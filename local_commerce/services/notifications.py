"""Durable, in-app Local Commerce order notifications."""

from contextvars import ContextVar

import frappe
from frappe.utils import now_datetime

from local_commerce.permissions.policy import MEMBER_ROLES
from local_commerce.services.owner import reject

_notification_operation = ContextVar("lc_notification_operation", default=False)


def _order_label(name):
    return "#" + str(name)[:8].upper()


def _shop_owners(shop):
    users = frappe.get_all(
        "LC Shop Member",
        filters={"shop": shop, "membership_role": "Owner", "enabled": 1},
        pluck="user",
        limit_page_length=0,
    )
    return {
        user
        for user in users
        if frappe.db.get_value("User", user, "enabled")
        and MEMBER_ROLES["Owner"] in frappe.get_roles(user)
    }


def _create(user, order, audience, title, message, target, seen):
    if not user or user == "Guest" or user == frappe.session.user or user in seen:
        return
    if not frappe.db.get_value("User", user, "enabled"):
        return
    seen.add(user)
    token = _notification_operation.set(True)
    try:
        notification = frappe.get_doc(
            {
                "doctype": "LC Notification",
                "recipient_user": user,
                "order": order.name,
                "shop": order.shop,
                "audience": audience,
                "title": title,
                "message": message,
                "target": target,
                "read": 0,
            }
        ).insert(ignore_permissions=True)
        frappe.enqueue(
            "local_commerce.services.push.send_notification",
            notification=notification.name,
            enqueue_after_commit=True,
            queue="short",
        )
    finally:
        _notification_operation.reset(token)


def packed_weight_updated(order):
    _create(
        order.customer_user,
        order,
        "Customer",
        "Your final bill is ready",
        "Your items have been weighed and the bill updated. Open your order to review the total.",
        "/orders",
        set(),
    )


def order_created(order):
    label = _order_label(order.name)
    seen = set()
    for user in _shop_owners(order.shop):
        _create(
            user,
            order,
            "Owner",
            f"New order {label}",
            f"{order.recipient} placed an order. Open it to accept or decline.",
            f"/shop/{order.shop}?tab=orders",
            seen,
        )


def status_changed(order, previous):
    label = _order_label(order.name)
    shop_name = frappe.db.get_value("LC Shop", order.shop, "shop_name") or "The shop"
    expired = order.status == "Cancelled" and order.reason == "Shop response timeout"
    customer_copy = {
        "Requested": ("Order received", f"Your order is with {shop_name}, awaiting confirmation."),
        "Accepted": (
            "Your order is accepted",
            f"{shop_name} accepted your order and will start preparing it soon.",
        ),
        "Preparing": ("Your order is being prepared", f"{shop_name} is getting your items ready."),
        "Ready": (
            "Your order is ready",
            "Your items are packed and waiting for the delivery person to collect them.",
        ),
        "Picked Up": (
            "Your order has been collected",
            f"Your delivery person has collected your order from {shop_name}.",
        ),
        "Out for Delivery": (
            "Your order is on its way",
            "Your delivery person is heading to you. Open your order for updates.",
        ),
        "Delivered": (
            "Your order has arrived",
            "Your delivery is complete. Thank you for shopping!",
        ),
        "Cancelled": (
            "Your order was cancelled",
            "Open your order to see the cancellation details.",
        ),
    }
    owner_copy = {
        "Requested": ("New order to review", "Open the order to accept or decline it."),
        "Accepted": ("Order accepted", "Start preparing the items for this order."),
        "Preparing": ("Preparation started", "The order is being prepared for collection."),
        "Ready": ("Order ready for collection", "Check the delivery assignment for this order."),
        "Picked Up": ("Order collected", "The delivery person has collected the order."),
        "Out for Delivery": (
            "Delivery is underway",
            "The delivery person is heading to the customer.",
        ),
        "Delivered": ("Order delivered", "Delivery is complete. Review payment and cash handover."),
        "Cancelled": (
            "Order cancelled",
            "Stop preparing this order and check the cancellation details.",
        ),
    }
    delivery_copy = {
        "Requested": ("Order awaiting confirmation", "Wait for the shop to confirm the order."),
        "Accepted": ("Shop accepted the order", "The shop will prepare this order for collection."),
        "Preparing": (
            "Shop is preparing your pickup",
            "Wait for the shop to mark the order ready.",
        ),
        "Ready": ("Your pickup is ready", "Collect the order from the shop and confirm pickup."),
        "Picked Up": (
            "Pickup confirmed",
            "When you leave, tap Start delivery to share your progress.",
        ),
        "Out for Delivery": (
            "Delivery started",
            "Follow the delivery address and keep location sharing on.",
        ),
        "Delivered": (
            "Delivery completed",
            "Thank you! Check your deliveries and any cash handover due.",
        ),
        "Cancelled": (
            "Delivery cancelled",
            "Do not continue this delivery. Check the order details.",
        ),
    }
    if expired:
        customer_copy["Cancelled"] = (
            "The shop could not confirm your order",
            f"{shop_name} did not respond in time, so your order was cancelled. You can try again.",
        )
        owner_copy["Cancelled"] = (
            "Order missed",
            "This order was cancelled because it was not accepted within the response time.",
        )
    seen = set()
    fallback = ("Order update", "Open the order to see the latest details.")
    title, message = customer_copy.get(order.status, fallback)
    _create(order.customer_user, order, "Customer", f"{title} · {label}", message, "/orders", seen)
    title, message = owner_copy.get(order.status, fallback)
    for user in _shop_owners(order.shop):
        _create(
            user,
            order,
            "Owner",
            f"{title} · {label}",
            f"{order.recipient}: {message}",
            f"/shop/{order.shop}?tab=orders",
            seen,
        )
    title, message = delivery_copy.get(order.status, fallback)
    _create(
        order.delivery_user,
        order,
        "Delivery Person",
        f"{title} · {label}",
        message,
        "/delivery",
        seen,
    )


def driver_assigned(order, previous_driver=None):
    label = _order_label(order.name)
    driver_name = (
        frappe.db.get_value("User", order.delivery_user, "full_name") or "Your delivery person"
    )
    seen = set()
    _create(
        order.customer_user,
        order,
        "Customer",
        f"Delivery person assigned · {label}",
        f"{driver_name} will handle your delivery. "
        "We’ll let you know when your order is on its way.",
        "/orders",
        seen,
    )
    _create(
        order.delivery_user,
        order,
        "Delivery Person",
        f"New delivery {label}",
        f"Collect an order for {order.recipient} from the shop.",
        "/delivery",
        seen,
    )
    if previous_driver and previous_driver != order.delivery_user:
        _create(
            previous_driver,
            order,
            "Delivery Person",
            f"Delivery {label} reassigned",
            "Another delivery person will handle this order. "
            "Check your list for your current deliveries.",
            "/delivery",
            seen,
        )
    for user in _shop_owners(order.shop):
        _create(
            user,
            order,
            "Owner",
            f"Delivery person assigned · {label}",
            f"{driver_name} is assigned to {order.recipient}'s delivery.",
            f"/shop/{order.shop}?tab=orders",
            seen,
        )


def list_notifications(start=0):
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please sign in to view notifications", frappe.AuthenticationError)
    try:
        start = int(start)
    except (TypeError, ValueError):
        reject("Invalid notification page")
    if start < 0:
        reject("Invalid notification page")
    rows = frappe.get_all(
        "LC Notification",
        filters={"recipient_user": user},
        fields=[
            "name",
            "order",
            "shop",
            "audience",
            "title",
            "message",
            "target",
            "read",
            "creation",
        ],
        order_by="creation desc",
        start=start,
        limit_page_length=20,
    )
    return {
        "items": rows,
        "unread": frappe.db.count("LC Notification", {"recipient_user": user, "read": 0}),
        "has_more": len(rows) == 20,
    }


def mark_read(name):
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please sign in to update notifications", frappe.AuthenticationError)
    notification = frappe.db.get_value(
        "LC Notification", {"name": name, "recipient_user": user}, ["name", "read"], as_dict=True
    )
    if not notification:
        frappe.throw("Notification access denied", frappe.PermissionError)
    if not notification.read:
        frappe.db.set_value(
            "LC Notification",
            notification.name,
            {"read": 1, "read_at": now_datetime()},
            update_modified=False,
        )
    return {"name": notification.name, "read": True}


def mark_all_read():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please sign in to update notifications", frappe.AuthenticationError)
    frappe.db.set_value(
        "LC Notification",
        {"recipient_user": user, "read": 0},
        {"read": 1, "read_at": now_datetime()},
        update_modified=False,
    )
    return {"read": True}


def upi_payment_updated(order):
    if order.payment_status == "Awaiting Verification":
        seen = set()
        for user in _shop_owners(order.shop):
            _create(user, order, "Owner", "UPI payment needs your review",
                    "A customer uploaded payment proof. Check your bank receipt before confirming.",
                    f"/shop/{order.shop}?tab=orders", seen)
    else:
        approved = order.payment_status == "Paid"
        _create(order.customer_user, order, "Customer",
                "Payment confirmed" if approved else "Please check your UPI payment",
                "The shop verified your payment. No cash is due at delivery." if approved
                else "The shop could not verify payment. Open your order for the review note.",
                "/orders", set())
