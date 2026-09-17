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
    _create(order.customer_user, order, "Customer", "Your packed weight and bill are ready",
            "The shop confirmed the actual packed weights. Open your order to see the final bill.",
            "/orders", set())


def order_created(order):
    label = _order_label(order.name)
    seen = set()
    for user in _shop_owners(order.shop):
        _create(
            user,
            order,
            "Owner",
            f"New order {label}",
            f"{order.recipient} placed a new delivery order.",
            f"/shop/{order.shop}?tab=orders",
            seen,
        )


def status_changed(order, previous):
    label = _order_label(order.name)
    shop_name = frappe.db.get_value("LC Shop", order.shop, "shop_name") or "Shop"
    expired = order.status == "Cancelled" and order.reason == "Shop response timeout"
    seen = set()
    _create(
        order.customer_user,
        order,
        "Customer",
        f"Order {label} expired" if expired else f"Order {label}: {order.status}",
        (
            f"{shop_name} did not confirm your order in time. Reserved stock was released."
            if expired
            else f"Your order from {shop_name} moved from {previous} to {order.status}."
        ),
        "/orders",
        seen,
    )
    for user in _shop_owners(order.shop):
        _create(
            user,
            order,
            "Owner",
            f"Order {label} expired" if expired else f"Order {label}: {order.status}",
            (
                f"{order.recipient}'s order was cancelled because it was not answered in time."
                if expired
                else f"{order.recipient}'s order moved from {previous} to {order.status}."
            ),
            f"/shop/{order.shop}?tab=orders",
            seen,
        )
    _create(
        order.delivery_user,
        order,
        "Driver",
        f"Delivery {label}: {order.status}",
        f"The delivery for {order.recipient} moved from {previous} to {order.status}.",
        "/delivery",
        seen,
    )


def driver_assigned(order, previous_driver=None):
    label = _order_label(order.name)
    driver_name = frappe.db.get_value("User", order.delivery_user, "full_name") or "A rider"
    seen = set()
    _create(
        order.customer_user,
        order,
        "Customer",
        f"Rider assigned to {label}",
        f"{driver_name} is assigned to your delivery.",
        "/orders",
        seen,
    )
    _create(
        order.delivery_user,
        order,
        "Driver",
        f"New delivery {label}",
        f"Collect an order for {order.recipient} from the shop.",
        "/delivery",
        seen,
    )
    if previous_driver and previous_driver != order.delivery_user:
        _create(
            previous_driver,
            order,
            "Driver",
            f"Delivery {label} reassigned",
            "This delivery is no longer assigned to you.",
            "/delivery",
            seen,
        )
    for user in _shop_owners(order.shop):
        _create(
            user,
            order,
            "Owner",
            f"Rider assigned to {label}",
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
        "unread": frappe.db.count(
            "LC Notification", {"recipient_user": user, "read": 0}
        ),
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
