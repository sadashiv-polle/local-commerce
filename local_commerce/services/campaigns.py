"""Explicitly approved promotional campaigns, separate from transactional alerts."""
import json
from contextvars import ContextVar
from datetime import timedelta
from urllib.parse import quote

import frappe
from frappe.utils import get_datetime, now_datetime
from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject

_operation = ContextVar("lc_campaign_operation", default=False)


def _user():
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Please sign in", frappe.AuthenticationError)
    return frappe.session.user


def preference(enabled=None):
    account = _user()
    name = frappe.db.get_value("LC Promotion Preference", {"user": account}, "name")
    if enabled is not None:
        if str(enabled) not in ("0", "1"):
            reject("Invalid preference")
        # Serialize first-time creation and consent changes.
        frappe.db.sql("select name from tabUser where name=%s for update", (account,))
        name = frappe.db.get_value("LC Promotion Preference", {"user": account}, "name")
        token = _operation.set(True)
        try:
            doc = frappe.get_doc("LC Promotion Preference", name) if name else frappe.new_doc("LC Promotion Preference")
            doc.update({"user": account, "enabled": int(enabled), "consented_at": now_datetime()})
            doc.save(ignore_permissions=True)
        finally:
            _operation.reset(token)
    return {"enabled": promotion_enabled(account)}


def _target(shop, item=""):
    if frappe.db.get_value("LC Shop", shop, "status") != "Active":
        reject("Choose an active shop")
    title = frappe.db.get_value("LC Shop", shop, "shop_name")
    if item:
        from local_commerce.services.orders import public_product
        product = public_product(shop, item)
        title = product["item_name"]
    return title


def options(shop=""):
    require_platform()
    shops = frappe.get_all("LC Shop", filters={"status": "Active"}, fields=["name", "shop_name"], limit_page_length=500)
    products = frappe.get_all("Item", filters={"lc_shop": shop, "disabled": 0},
                              fields=["name", "item_name"], limit_page_length=500) if shop else []
    return {"shops": shops, "products": products}


def listing():
    require_platform()
    rows = frappe.get_all("LC Campaign", fields=["name", "title", "message", "status", "send_at", "queued_count", "skipped_count"],
                          order_by="creation desc", limit_page_length=50)
    for row in rows:
        row["read_count"] = frappe.db.count("LC Notification", {"campaign": row.name, "campaign_test": 0, "read": 1})
    return rows


def save(shop, title, message, item=""):
    require_platform()
    _target(shop, item)
    title, message = str(title).strip(), str(message).strip()
    if not 1 <= len(title) <= 80 or not 1 <= len(message) <= 240:
        reject("Use a title up to 80 characters and a message up to 240 characters")
    token = _operation.set(True)
    try:
        doc = frappe.get_doc({"doctype": "LC Campaign", "shop": shop, "item": item,
                              "title": title, "message": message, "status": "Draft"}).insert(ignore_permissions=True)
    finally:
        _operation.reset(token)
    return {"name": doc.name}


def _lock(name):
    frappe.db.sql("select name from `tabLC Campaign` where name=%s for update", (name,))
    return frappe.get_doc("LC Campaign", name)


def send(name, send_at=""):
    require_platform()
    doc = _lock(name)
    if doc.status != "Draft":
        return {"status": doc.status}
    _target(doc.shop, doc.item)
    when = get_datetime(send_at) if send_at else now_datetime()
    if send_at and when < now_datetime():
        reject("Choose a future time")
    # Snapshot consented users; opt-outs and enabled accounts are checked again by the worker.
    users = set(frappe.get_all("LC Promotion Preference", filters={"enabled": 1}, pluck="user", limit_page_length=0))
    users.update(frappe.get_all("LC Push Subscription", filters={"enabled": 1}, pluck="user", limit_page_length=0))
    users = sorted(account for account in users if allowed(account))
    frappe.db.set_value("LC Campaign", name, {"status": "Queued", "send_at": when, "recipients": json.dumps(users)})
    return {"status": "Queued"}


def cancel(name):
    require_platform()
    doc = _lock(name)
    if doc.status in ("Draft", "Queued"):
        frappe.db.set_value("LC Campaign", name, "status", "Cancelled")
    return {"status": frappe.db.get_value("LC Campaign", name, "status")}


def _notify(doc, account, test=False):
    from local_commerce.services.notifications import _notification_operation
    token = _notification_operation.set(True)
    try:
        notification = frappe.get_doc({
            "doctype": "LC Notification", "recipient_user": account, "shop": doc.shop,
            "item": doc.item, "campaign": doc.name, "campaign_test": int(test), "audience": "Customer",
            "title": ("[Test] " if test else "") + doc.title, "message": doc.message,
            "target": f'/store/{quote(doc.shop, safe="")}' + (f'?item={quote(doc.item, safe="")}' if doc.item else ""),
        }).insert(ignore_permissions=True)
        frappe.enqueue("local_commerce.services.push.send_notification", notification=notification.name,
                       enqueue_after_commit=True, queue="short")
    finally:
        _notification_operation.reset(token)


def test(name):
    require_platform()
    doc = frappe.get_doc("LC Campaign", name)
    _target(doc.shop, doc.item)
    if not frappe.db.exists("LC Push Subscription", {"user": _user(), "enabled": 1}):
        reject("Enable phone notifications on your administrator account first")
    _notify(doc, _user(), test=True)
    return {"status": "Test queued to your account"}


def promotion_enabled(account):
    # Explicit opt-outs take precedence over device registration and refreshes.
    preference = frappe.db.get_value("LC Promotion Preference", {"user": account}, "enabled")
    if preference is not None:
        return bool(preference)
    return bool(frappe.db.exists("LC Push Subscription", {"user": account, "enabled": 1}))


def allowed(account):
    return bool(frappe.db.get_value("User", account, "enabled") and
                promotion_enabled(account))


def process_one(name):
    doc = _lock(name)
    now = now_datetime()
    if doc.status != "Queued" or get_datetime(doc.send_at) > now or not 9 <= now.hour < 20:
        return
    _target(doc.shop, doc.item)
    users = json.loads(doc.recipients or "[]")
    cursor, queued, skipped = doc.cursor or 0, doc.queued_count or 0, doc.skipped_count or 0
    for account in users[cursor:cursor + 100]:
        # Serialize campaigns for the same user so concurrent workers respect the cap.
        frappe.db.sql("select name from tabUser where name=%s for update", (account,))
        recent = frappe.db.count("LC Notification", {
            "recipient_user": account, "campaign": ["is", "set"], "campaign_test": 0,
            "creation": [">=", now - timedelta(days=7)],
        })
        if allowed(account) and recent < 2:
            _notify(doc, account)
            queued += 1
        else:
            skipped += 1
        cursor += 1
    frappe.db.set_value("LC Campaign", name, {
        "cursor": cursor, "queued_count": queued, "skipped_count": skipped,
        "status": "Completed" if cursor >= len(users) else "Queued",
    })


def process_pending():
    for name in frappe.get_all("LC Campaign", filters={"status": "Queued", "send_at": ["<=", now_datetime()]},
                               pluck="name", order_by="send_at asc", limit_page_length=20):
        try:
            process_one(name)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="Promotional campaign failed", message=frappe.get_traceback())
