"""Explicitly approved promotional campaigns, separate from transactional alerts."""
import json
import hashlib
from datetime import timedelta
from contextvars import ContextVar
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
                              fields=["name", "item_name", "item_group"], limit_page_length=500) if shop else []
    from local_commerce.services.campaign_templates import library, settings
    return {"shops": shops, "products": products, "templates": library(), "template_settings": settings()}


def listing():
    require_platform()
    rows = frappe.get_all("LC Campaign", fields=["name", "title", "message", "automatic_key", "status", "send_at", "queued_count", "skipped_count", "template_id", "template_script", "campaign_audience"],
                          order_by="creation desc", limit_page_length=50)
    for row in rows:
        row["suppressed_count"] = frappe.db.count("LC Notification", {"campaign": row.name, "campaign_test": 0, "campaign_push_state": "Expired"})
        row["read_count"] = frappe.db.count("LC Notification", {"campaign": row.name, "campaign_test": 0, "read": 1})
    return rows


def save(shop, title, message, item="", template_id="", template_script="latin", campaign_audience="All", campaign_period=""):
    require_platform()
    _target(shop, item)
    from local_commerce.services.campaign_templates import validate_campaign
    validate_campaign(template_id, template_script, item, campaign_audience, campaign_period)
    title, message = str(title).strip(), str(message).strip()
    if not 1 <= len(title) <= 80 or not 1 <= len(message) <= 240:
        reject("Use a title up to 80 characters and a message up to 240 characters")
    token = _operation.set(True)
    try:
        doc = frappe.get_doc({"doctype": "LC Campaign", "shop": shop, "item": item,
                              "title": title, "message": message, "status": "Draft",
                              "template_id": template_id, "template_script": template_script,
                              "campaign_audience": campaign_audience, "campaign_period": campaign_period}).insert(ignore_permissions=True)
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
    from local_commerce.services.campaign_templates import validate_campaign, delivery_state
    validate_campaign(doc.get('template_id'), doc.get('template_script') or 'latin', doc.item,
                      doc.get('campaign_audience') or 'All', doc.get('campaign_period') or '')
    state = delivery_state(doc, when)
    if state != 'ready':
        reject('Choose a time within the template day, sending window and Goan hours' if state == 'wait' else state)
    # Snapshot consented users; opt-outs and enabled accounts are checked again by the worker.
    users = set(frappe.get_all("LC Promotion Preference", filters={"enabled": 1}, pluck="user", limit_page_length=0))
    users.update(frappe.get_all("LC Push Subscription", filters={"enabled": 1}, pluck="user", limit_page_length=0))
    users = sorted(account for account in users if allowed(account))
    if doc.get('campaign_audience') == 'Shop customers':
        customers = set(frappe.get_all('LC Order', filters={'shop': doc.shop}, pluck='customer_user', limit_page_length=0))
        users = [account for account in users if account in customers]
    frappe.db.set_value("LC Campaign", name, {"status": "Queued", "send_at": when, "recipients": json.dumps(users)})
    return {"status": "Queued"}


def cancel(name):
    require_platform()
    doc = _lock(name)
    if doc.status in ("Draft", "Queued") or doc.get("automatic_key"):
        frappe.db.set_value("LC Campaign", name, "status", "Cancelled")
    return {"status": frappe.db.get_value("LC Campaign", name, "status")}


def _notify(doc, account, test=False):
    # Production callers hold the campaign row lock; repeated jobs reuse the record.
    if not test and frappe.db.exists('LC Notification', {
        'campaign': doc.name, 'recipient_user': account, 'campaign_test': 0,
    }):
        return False
    from local_commerce.services.notifications import _notification_operation
    token = _notification_operation.set(True)
    try:
        notification = frappe.get_doc({
            "doctype": "LC Notification", "recipient_user": account, "shop": doc.shop,
            "item": doc.item, "campaign": doc.name, "campaign_test": int(test), "audience": "Customer",
            "campaign_push_state": "" if test else "Pending",
            "title": ("[Test] " if test else "") + doc.title, "message": doc.message,
            "target": f'/store/{quote(doc.shop, safe="")}' + (f'?item={quote(doc.item, safe="")}' if doc.item else ""),
        }).insert(ignore_permissions=True)
        frappe.enqueue("local_commerce.services.push.send_notification", notification=notification.name,
                       enqueue_after_commit=True, queue="short")
    finally:
        _notification_operation.reset(token)
    return True


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


def shop_is_open(shop, current=None):
    from local_commerce.services.shop_hours import availability
    doc = frappe.get_doc("LC Shop", shop)
    if doc.status != "Active" or not doc.opening_hours_json:
        return False
    return availability(doc, current=current)["open"]


def process_one(name):
    doc = _lock(name)
    now = now_datetime()
    if doc.status != "Queued" or get_datetime(doc.send_at) > now or not shop_is_open(doc.shop, now):
        return
    from local_commerce.services.campaign_templates import delivery_state
    state = delivery_state(doc, now)
    if state == 'wait':
        return
    users = json.loads(doc.recipients or "[]")
    cursor, queued, skipped = doc.cursor or 0, doc.queued_count or 0, doc.skipped_count or 0
    for account in users[cursor:cursor + 100]:
        if not shop_is_open(doc.shop):
            break
        # Serialize campaigns for the same user so concurrent workers respect the cap.
        frappe.db.sql("select name from tabUser where name=%s for update", (account,))
        if state == 'ready' and allowed(account):
            if _notify(doc, account):
                queued += 1
        else:
            skipped += 1
        cursor += 1
    frappe.db.set_value("LC Campaign", name, {
        "cursor": cursor, "queued_count": queued, "skipped_count": skipped,
        "status": "Completed" if cursor >= len(users) else "Queued",
    })


def process_pending():
    deliver_pending_promotions()
    for name in frappe.get_all("LC Campaign", filters={"status": "Queued", "send_at": ["<=", now_datetime()]},
                               pluck="name", order_by="send_at asc", limit_page_length=20):
        try:
            process_one(name)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="Promotional campaign failed", message=frappe.get_traceback())

    process_daily()

def wording_history(shop, item=""):
    require_platform()
    filters = {"shop": shop}
    if item:
        filters["item"] = item
    else:
        filters["item"] = ["is", "not set"]
    return frappe.get_all("LC Campaign", filters=filters, fields=["title", "message"],
                          order_by="creation desc, name desc", limit_page_length=0)


def automatic_due(account, now):
    rows = frappe.db.sql("""
        select count(case when n.creation >= %s then 1 end) as today_count,
               max(n.creation) as last_sent
        from `tabLC Notification` n
        inner join `tabLC Campaign` c on c.name = n.campaign
        where n.recipient_user = %s and n.campaign_test = 0
          and c.automatic_key is not null and c.automatic_key != ''
    """, (now.replace(hour=0, minute=0, second=0, microsecond=0), account), as_dict=True)
    row = rows[0]
    return int(row.today_count or 0) < 5 and (
        not row.last_sent or now - get_datetime(row.last_sent) >= timedelta(minutes=150)
    )


def daily_wording(product, shop_name, day):
    import re
    from pathlib import Path
    copy = json.loads((Path(__file__).resolve().parents[1] / "campaign_copy.json").read_text())
    theme = next((row["ideas"] for row in copy["themes"]
                  if re.search(row["pattern"], product.get("item_group") or "", re.I)), copy["general"])
    title, template = theme[day % len(theme)]
    message = template.replace("{selection}", f'{product["item_name"]} at {shop_name}')
    return title, message if len(message) <= 240 else template.replace("{selection}", "this product in the shop")


def process_daily():
    """Up to five automatic attempts daily, at least 150 minutes apart across shops."""
    from local_commerce.services.orders import public_product
    from local_commerce.services.stock_alerts import restocked

    now = now_datetime()
    shops = frappe.get_all("LC Shop", filters={"status": "Active"}, pluck="name", order_by="name asc", limit_page_length=0)
    if not shops:
        return
    slot = (now.hour * 60 + now.minute) // 150
    rotation = now.date().toordinal() * 10 + slot
    offset = rotation % len(shops)
    for shop in shops[offset:] + shops[:offset]:
        try:
            # Serialize daily campaign creation for this shop.
            frappe.db.sql("select name from `tabLC Shop` where name=%s for update", (shop,))
            if not shop_is_open(shop, now):
                frappe.db.commit()
                continue
            items = frappe.get_all("Item", filters={"lc_shop": shop, "disabled": 0},
                                   pluck="name", order_by="name asc", limit_page_length=0)
            if not items:
                frappe.db.commit()
                continue
            shift = rotation % len(items)
            product = None
            for item in items[shift:] + items[:shift]:
                try:
                    candidate = public_product(shop, item)
                    if restocked(candidate):
                        product = candidate
                        break
                except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError):
                    continue
            if not product:
                frappe.db.commit()
                continue
            key = hashlib.sha256(f"{now.date()}:{slot}:{shop}".encode()).hexdigest()
            name = frappe.db.get_value("LC Campaign", {"automatic_key": key}, "name")
            if not name:
                title, message = daily_wording(product, frappe.db.get_value("LC Shop", shop, "shop_name"), rotation)
                from local_commerce.services.campaign_templates import automatic_choice
                choice = automatic_choice(shop, item, now) or {}
                title, message = choice.get('title', title), choice.get('message', message)
                token = _operation.set(True)
                try:
                    campaign = frappe.get_doc({"doctype": "LC Campaign", "shop": shop, "item": item,
                        "title": title, "message": message, "automatic_key": key, "status": "Completed",
                        "send_at": now, "template_id": choice.get("template_id"),
                        "template_script": choice.get("template_script")}).insert(ignore_permissions=True)
                    name = campaign.name
                finally:
                    _operation.reset(token)
            campaign = _lock(name)
            if campaign.status == "Cancelled":
                frappe.db.commit()
                continue
            # Validate the saved daily product again, including stock changes since creation.
            if not restocked(public_product(shop, campaign.item)):
                frappe.db.commit()
                continue
            from local_commerce.services.campaign_templates import delivery_state
            if delivery_state(campaign, now) != 'ready':
                frappe.db.commit()
                continue
            users = set(frappe.get_all("LC Promotion Preference", filters={"enabled": 1}, pluck="user", limit_page_length=0))
            users.update(frappe.get_all("LC Push Subscription", filters={"enabled": 1}, pluck="user", limit_page_length=0))
            sent = 0
            for account in sorted(users):
                if not shop_is_open(shop):
                    break
                frappe.db.sql("select name from tabUser where name=%s for update", (account,))
                if allowed(account) and automatic_due(account, now):
                    if _notify(campaign, account):
                        sent += 1
                if sent >= 100:
                    break
            if sent:
                frappe.db.set_value("LC Campaign", name, "queued_count", (campaign.queued_count or 0) + sent)
            frappe.db.commit()
            if sent:
                return
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="Daily promotion failed", message=frappe.get_traceback())


def deliver_pending_promotions():
    from local_commerce.services.push import send_notification
    for name in frappe.get_all("LC Notification", filters={"campaign_push_state": "Pending"},
                               pluck="name", order_by="creation asc", limit_page_length=200):
        try:
            send_notification(name)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="Pending promotional push failed", message=frappe.get_traceback())
