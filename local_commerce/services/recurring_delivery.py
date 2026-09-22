"""Time-only daily schedules produce separate, immutable dated booking batches."""

from datetime import timedelta

import frappe
from frappe.utils import now_datetime

from local_commerce.permissions.scope import require_schedule
from local_commerce.services.owner import reject
from local_commerce.services.schedule_rules import daily_window

FIELDS = [
    "title", "enabled", "ordering_start", "ordering_end", "delivery_start", "delivery_end",
    "capacity", "products", "postcodes", "radius_km",
]


def validate_schedule(doc):
    require_schedule(doc.shop)
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    old = doc.get_doc_before_save()
    if old and old.shop != doc.shop:
        reject("Create a new daily schedule to use another shop")
    try:
        daily_window(now_datetime().date(), [doc.get(f) for f in FIELDS[2:6]])
        if not 1 <= int(doc.capacity) <= 30 or float(doc.capacity) != int(doc.capacity):
            raise ValueError("Maximum orders must be a whole number from 1 to 30")
        if not 0 < float(doc.radius_km) <= 500:
            raise ValueError("Set a delivery radius greater than 0 and at most 500 km")
    except (TypeError, ValueError) as exc:
        reject(str(exc))
    for item in str(doc.products or "").splitlines():
        if item.strip() and not frappe.db.exists(
            "Item", {"name": item.strip(), "lc_shop": doc.shop}
        ):
            reject("Select products belonging to this shop")


def save_schedule(shop, values, name=None):
    require_schedule(shop)
    values = frappe.parse_json(values)
    doc = frappe.get_doc("LC Delivery Schedule", name) if name else frappe.new_doc(
        "LC Delivery Schedule"
    )
    if name and doc.shop != shop:
        reject("Daily schedule belongs to another shop")
    doc.shop = shop
    doc.update({key: values[key] for key in FIELDS if key in values})
    doc.save(ignore_permissions=True)
    return doc.name


def sync_schedule(schedule):
    # The same lock serializes edits, checkout and scheduler generation.
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", schedule.shop)
    schedule = frappe.get_doc("LC Delivery Schedule", schedule.name)
    today = now_datetime().date()
    for offset in (0, 1):
        date = today + timedelta(days=offset)
        times = daily_window(date, [schedule.get(f) for f in FIELDS[2:6]])
        if times[-1] <= now_datetime():
            continue
        identity = f"daily-{schedule.name}-{date.isoformat()}"
        exists = frappe.db.exists("LC Delivery Slot", identity)
        slot = frappe.get_doc("LC Delivery Slot", identity) if exists else frappe.new_doc(
            "LC Delivery Slot"
        )
        if exists and slot.get("archived"):
            continue
        before = {f: str(slot.get(f) or "") for f in FIELDS} if exists else None
        booked = exists and frappe.db.exists("LC Order", {"scheduled_slot": identity})
        if exists and not booked and slot.delivery_end < now_datetime():
            continue
        if not booked:
            slot.shop = schedule.shop
            slot.daily_schedule = schedule.name
            slot.update({field: schedule.get(field) for field in FIELDS})
            slot.update(dict(zip(FIELDS[2:6], times)))
            if not exists or slot.ordering_end > now_datetime():
                slot.compiled = 0
        # Visibility changes apply immediately; booked dates/prices/areas remain unchanged.
        slot.enabled = schedule.enabled
        if before == {f: str(slot.get(f) or "") for f in FIELDS}:
            continue
        slot.flags.daily_generation = True
        if exists:
            slot.save(ignore_permissions=True)
        else:
            slot.insert(ignore_permissions=True, set_name=identity)


def generate_daily():
    for name in frappe.get_all("LC Delivery Schedule", pluck="name", limit_page_length=0):
        frappe.db.savepoint("daily_schedule")
        try:
            sync_schedule(frappe.get_doc("LC Delivery Schedule", name))
        except Exception:
            frappe.db.rollback(save_point="daily_schedule")
            frappe.log_error(title="Daily delivery schedule generation failed")


def remove_schedule(name):
    doc = frappe.get_doc("LC Delivery Schedule", name)
    require_schedule(doc.shop)
    frappe.delete_doc("LC Delivery Schedule", name, ignore_permissions=True)
    return {"deleted": True}


def cleanup_schedule(doc):
    require_schedule(doc.shop)
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    for name in frappe.get_all("LC Delivery Slot", filters={"daily_schedule": doc.name},
                               pluck="name", limit_page_length=0):
        if frappe.db.exists("LC Order", {"scheduled_slot": name}):
            frappe.db.set_value("LC Delivery Slot", name, {"daily_schedule": None, "enabled": 0})
        else:
            frappe.delete_doc("LC Delivery Slot", name, ignore_permissions=True)
