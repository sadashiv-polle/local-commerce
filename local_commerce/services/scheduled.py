"""Scheduled bookings: one shop and delivery period per bounded batch."""

import frappe
from frappe.utils import get_datetime, now_datetime

from local_commerce.permissions.scope import require_platform, require_shop
from local_commerce.services.owner import reject
from local_commerce.services.schedule_rules import window

SLOT_FIELDS = [
    "name",
    "title",
    "ordering_start",
    "ordering_end",
    "delivery_start",
    "delivery_end",
    "capacity",
    "products",
    "postcodes",
    "radius_km",
    "enabled",
    "compiled",
]


def lines(value):
    return {part.strip().upper() for part in str(value or "").splitlines() if part.strip()}


def validate_slot(doc):
    require_platform()
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    try:
        window(doc.ordering_start, doc.ordering_end, doc.delivery_start, doc.delivery_end)
        if not 1 <= int(doc.capacity) <= 30 or float(doc.capacity) != int(doc.capacity):
            raise ValueError("Batch capacity must be a whole number from 1 to 30")
        if not 0 < float(doc.radius_km) <= 500:
            raise ValueError("Set a delivery radius from 0 to 500 km")
    except (TypeError, ValueError) as exc:
        reject(str(exc))
    for field in ("ordering_start", "ordering_end", "delivery_start", "delivery_end"):
        setattr(doc, field, get_datetime(doc.get(field)))
    old = doc.get_doc_before_save()
    if old and frappe.db.exists("LC Order", {"scheduled_slot": doc.name}):
        for field in (
            "shop",
            "ordering_start",
            "ordering_end",
            "delivery_start",
            "delivery_end",
            "products",
            "postcodes",
            "radius_km",
            "capacity",
        ):
            if str(old.get(field) or "") != str(doc.get(field) or ""):
                reject(
                    "This slot has bookings. Disable new bookings "
                    "and create a new slot to change it"
                )
    overlap = frappe.db.sql(
        """select name from `tabLC Delivery Slot` where shop=%s
        and name!=%s and delivery_start < %s and delivery_end > %s limit 1""",
        (doc.shop, doc.name or "", doc.delivery_end, doc.delivery_start),
    )
    if overlap:
        reject("Use one slot for each shop delivery period; delivery periods cannot overlap")
    for item in str(doc.products or "").splitlines():
        if item.strip() and not frappe.db.exists(
            "Item", {"name": item.strip(), "lc_shop": doc.shop}
        ):
            reject("Select products belonging to this shop")


def slots(shop, admin=False):
    if admin:
        require_shop(shop)
    else:
        doc = frappe.get_doc("LC Shop", shop)
        if doc.status != "Active" or not doc.get("scheduled_enabled"):
            return []
    filters = {"shop": shop, "delivery_end": [">", now_datetime()]}
    if not admin:
        filters["enabled"] = 1
    rows = frappe.get_all(
        "LC Delivery Slot",
        filters=filters,
        fields=SLOT_FIELDS,
        order_by="delivery_start asc",
        limit_page_length=100,
    )
    for row in rows:
        row["order_count"] = frappe.db.count(
            "LC Order", {"scheduled_slot": row.name, "status": ["!=", "Cancelled"]}
        )
        row["bookable"] = (
            row.enabled
            and get_datetime(row.ordering_start) <= now_datetime() < get_datetime(row.ordering_end)
            and row.order_count < row.capacity
        )
    return rows


def save_slot(shop, values, name=None):
    require_platform()
    values = frappe.parse_json(values)
    doc = frappe.get_doc("LC Delivery Slot", name) if name else frappe.new_doc("LC Delivery Slot")
    if name and doc.shop != shop:
        reject("Slot belongs to another shop")
    doc.shop = shop
    doc.update(
        {
            key: values[key]
            for key in SLOT_FIELDS
            if key in values and key not in {"name", "compiled"}
        }
    )
    doc.save(ignore_permissions=True)
    return doc.name


def configure(shop, normal, scheduled):
    require_platform()
    doc = frappe.get_doc("LC Shop", shop)
    doc.delivery_enabled = int(str(normal) in {"1", "True", "true"})
    doc.scheduled_enabled = int(str(scheduled) in {"1", "True", "true"})
    doc.save(ignore_permissions=True)
    return settings(shop)


def settings(shop):
    require_shop(shop)
    doc = frappe.get_doc("LC Shop", shop)
    return {
        "normal": bool(doc.delivery_enabled),
        "scheduled": bool(doc.get("scheduled_enabled")),
        "slots": slots(shop, admin=True),
        "timezone": frappe.utils.get_system_timezone(),
    }


def validate_booking(shop, mode, slot_name, rows, address=None):
    if mode not in {"Normal", "Scheduled"}:
        reject("Choose Normal or Scheduled delivery")
    if mode == "Normal":
        if not shop.delivery_enabled:
            reject("Normal delivery is disabled for this shop")
        return None
    if not shop.get("scheduled_enabled") or not slot_name:
        reject("Choose an available scheduled delivery slot")
    # Checkout already holds the shop lock, shared with slot edits and compilation.
    slot = frappe.get_doc("LC Delivery Slot", slot_name)
    if slot.shop != shop.name or not slot.enabled:
        reject("This scheduled delivery slot is unavailable")
    if not get_datetime(slot.ordering_start) <= now_datetime() < get_datetime(slot.ordering_end):
        reject("The ordering window for this scheduled delivery is closed")
    count = frappe.db.count(
        "LC Order", {"scheduled_slot": slot.name, "status": ["!=", "Cancelled"]}
    )
    if count >= slot.capacity:
        reject("This scheduled delivery slot is fully booked")
    allowed = {v.strip() for v in (slot.products or "").splitlines() if v.strip()}
    if allowed and any(row["item"] not in allowed for row in rows):
        reject("Some cart products are not available in this scheduled delivery slot")
    if address is not None:
        from local_commerce.services.location_rules import distance_km, point
        from local_commerce.services.locations import shop_location

        destination = point(address.get("latitude"), address.get("longitude"), required=True)
        origin = shop_location(shop)
        if not origin or distance_km(origin, destination) > slot.radius_km:
            reject("This address is outside the scheduled delivery area")
        if lines(slot.postcodes) and str(address.get("postal_code", "")).upper() not in lines(
            slot.postcodes
        ):
            reject("This postal code is outside the scheduled delivery zone")
    return slot


def compile_due():
    for row in frappe.get_all(
        "LC Delivery Slot",
        filters={"compiled": 0, "ordering_end": ["<=", now_datetime()]},
        fields=["name", "shop"],
        limit_page_length=100,
    ):
        frappe.db.sql("select name from `tabLC Shop` where name=%s for update", row.shop)
        if frappe.db.get_value("LC Delivery Slot", row.name, "compiled"):
            continue
        # Orders link to the slot at checkout; closing it forms the immutable membership cutoff.
        frappe.db.set_value("LC Delivery Slot", row.name, "compiled", 1)
        frappe.enqueue(
            "local_commerce.services.scheduled.prepare_route",
            slot_name=row.name,
            enqueue_after_commit=True,
            queue="short",
        )


def prepare_route(slot_name):
    from local_commerce.services.locations import shop_location
    from local_commerce.services.routing import batch_route

    slot = frappe.get_doc("LC Delivery Slot", slot_name)
    stops = frappe.get_all(
        "LC Order",
        filters={"scheduled_slot": slot_name, "status": ["not in", ["Cancelled", "Delivered"]]},
        fields=["destination_latitude", "destination_longitude"],
        order_by="creation asc, name asc",
        limit_page_length=30,
    )
    if stops:
        try:
            batch_route(
                shop_location(frappe.get_doc("LC Shop", slot.shop)),
                [
                    {"latitude": stop.destination_latitude, "longitude": stop.destination_longitude}
                    for stop in stops
                ],
            )
        except Exception:
            frappe.log_error(
                title="Scheduled route unavailable",
                message="Batch " + slot_name + ": retry route in shop workspace",
            )


def batch(slot_name):
    from local_commerce.services import orders

    slot = frappe.get_doc("LC Delivery Slot", slot_name)
    names = frappe.get_all(
        "LC Order",
        filters={"scheduled_slot": slot.name, "status": ["!=", "Cancelled"]},
        pluck="name",
        order_by="creation asc, name asc",
        limit_page_length=31,
    )
    is_rider = (
        frappe.session.user != "Guest"
        and all(
            frappe.db.get_value("LC Order", name, "delivery_user") == frappe.session.user
            for name in names
        )
        and bool(names)
    )
    if not is_rider:
        require_shop(slot.shop)
    if get_datetime(slot.ordering_end) > now_datetime():
        reject("The batch will be available after its ordering window closes")
    return slot, [orders.detail(name) for name in names]


def assign(slot_name, delivery_user):
    from local_commerce.services import orders

    slot = frappe.get_doc("LC Delivery Slot", slot_name)
    require_platform()
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", slot.shop)
    _, rows = batch(slot_name)
    if not rows or any(row["status"] != "Ready" for row in rows):
        reject("All active batch orders must be Ready before assigning the batch")
    for row in rows:
        orders.assign_driver(row["name"], delivery_user)
    return {"assigned": len(rows)}


def route(slot_name):
    from local_commerce.services.locations import map_config, shop_location
    from local_commerce.services.routing import batch_route

    slot, rows = batch(slot_name)
    rows = [row for row in rows if row["status"] != "Delivered"]
    origin = shop_location(frappe.get_doc("LC Shop", slot.shop))
    if not rows:
        return {"stops": [], "points": [], "map": map_config(), "title": slot.title}
    if not origin:
        reject("The shop needs a map location to generate a batch route")
    result = dict(batch_route(origin, [row["destination_location"] for row in rows]))
    result["stops"] = [rows[index] for index in result.pop("sequence")]
    result.update(
        map=map_config(),
        origin=origin,
        title=slot.title,
        delivery_start=slot.delivery_start,
        delivery_end=slot.delivery_end,
    )
    return result


def rider_batches():
    from local_commerce.services.orders import driver_shops

    shops = driver_shops()
    return frappe.get_all(
        "LC Order",
        filters={
            "delivery_user": frappe.session.user,
            "shop": ["in", shops],
            "delivery_mode": "Scheduled",
            "status": ["in", ["Ready", "Picked Up", "Out for Delivery"]],
        },
        fields=["scheduled_slot"],
        group_by="scheduled_slot",
        limit_page_length=100,
    )
