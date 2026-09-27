import json
from urllib.parse import quote

import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject
from local_commerce.services.payments import cashfree
from local_commerce.services.payments.rules import valid_signature


@frappe.whitelist(methods=["GET"])
def settings():
    require_platform()
    return {
        "profiles": frappe.get_all("LC Payment Gateway", fields=["name", "enabled", "environment"]),
        "shops": frappe.get_all(
            "LC Shop",
            fields=["name", "shop_name", "company", *cashfree.SHOP_FIELDS],
            limit_page_length=0,
        ),
        "accounts": frappe.get_all(
            "Account",
            filters={
                "is_group": 0,
                "disabled": 0,
                "account_currency": "INR",
                "root_type": ["in", ["Asset", "Expense"]],
            },
            fields=["name", "company", "root_type", "account_type"],
            limit_page_length=0,
        ),
        "modes": frappe.get_all("Mode of Payment", filters={"type": "Bank"}, pluck="name"),
        "webhook_url": frappe.utils.get_url("/api/method/local_commerce.api.cashfree.webhook"),
        "orders": frappe.get_all(
            "LC Order",
            filters={"payment_method": "Cashfree"},
            fields=[
                "name",
                "shop",
                "status",
                "payment_status",
                "gateway_order_id",
                "gateway_payment_id",
                "gateway_accounting_error",
                "payment_entry",
            ],
            order_by="creation desc",
            limit_page_length=50,
        ),
    }


@frappe.whitelist(methods=["POST"])
def save_profile(name, enabled=0, environment="sandbox", client_id="", client_secret=""):
    require_platform()
    if environment not in {"sandbox", "production"}:
        reject("Select Sandbox or Production")
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        reject("Enter a gateway profile name")
    exists = frappe.db.exists("LC Payment Gateway", name)
    doc = (
        frappe.get_doc("LC Payment Gateway", name)
        if exists
        else frappe.new_doc("LC Payment Gateway")
    )
    if not exists:
        doc.name = name
    doc.enabled = int(str(enabled) in {"1", "True", "true"})
    doc.environment = environment
    if client_id:
        doc.client_id = client_id.strip()
    if client_secret:
        doc.client_secret = client_secret.strip()
    if not doc.client_id or not (
        client_secret or (exists and doc.get_password("client_secret", raise_exception=False))
    ):
        reject("Enter the Cashfree Client ID and Secret")
    doc.save(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def save_shop(shop, values):
    require_platform()
    values = frappe.parse_json(values)
    if not isinstance(values, dict) or set(values) - set(cashfree.SHOP_FIELDS):
        reject("Invalid Cashfree settings")
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", shop)
    doc = frappe.get_doc("LC Shop", shop)
    for field, value in values.items():
        doc.set(field, value)
    cashfree.validate_shop(doc)
    doc.save(ignore_permissions=True)
    return {"saved": True}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def checkout(order):
    return cashfree.checkout(order)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=120, seconds=3600)
def verify(order):
    return cashfree.sync(order)


@frappe.whitelist(methods=["POST"])
def vendor_status(shop):
    require_platform()
    doc = frappe.get_doc("LC Shop", shop)
    result = cashfree.request(
        doc.cashfree_gateway,
        "GET",
        "/easy-split/vendors/" + quote(doc.cashfree_vendor_id or "", safe=""),
    )
    return {key: result.get(key) for key in ("vendor_id", "status", "name", "schedule_option")}


@frappe.whitelist(methods=["POST"])
def settlements(order):
    require_platform()
    doc = frappe.get_doc("LC Order", order)
    if doc.payment_method != "Cashfree":
        reject("This order does not use Cashfree")
    result = cashfree.request(
        doc.gateway_profile, "GET", "/easy-split/orders/" + quote(doc.gateway_order_id, safe="")
    )
    return {"split": json.loads(doc.gateway_snapshot), "settlement": result}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook(**kwargs):
    # Read the exact bytes Cashfree signed, before any JSON re-serialization.
    raw = frappe.request.get_data()
    if len(raw) > 262144:
        frappe.throw("Payload too large", frappe.PermissionError)
    try:
        payload = json.loads(raw)
        data = payload["data"]
        order_id = (
            data.get("order", {}).get("order_id")
            or data.get("refund", {}).get("order_id")
            or data.get("order_id")
        )
        if not isinstance(order_id, str):
            raise ValueError("Missing order ID")
    except (ValueError, KeyError, TypeError, AttributeError):
        frappe.throw("Invalid webhook", frappe.PermissionError)
    order = frappe.db.get_value(
        "LC Order", {"gateway_order_id": order_id}, ["name", "gateway_profile"], as_dict=True
    )
    if not order:
        frappe.throw("Unknown payment", frappe.PermissionError)
    profile = frappe.get_doc("LC Payment Gateway", order.gateway_profile)
    if not valid_signature(
        profile.get_password("client_secret"),
        frappe.request.headers.get("x-webhook-timestamp", ""),
        raw,
        frappe.request.headers.get("x-webhook-signature", ""),
    ):
        frappe.throw("Invalid webhook signature", frappe.PermissionError)
    # Every replay rechecks the provider; row locks and payment references prevent duplicates.
    cashfree.sync(order.name, authorize=False)
    return {"received": True}
