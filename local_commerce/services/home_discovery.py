"""Public home cards, using existing shop discovery and private address authorization."""
import frappe
from frappe.utils import now_datetime

from local_commerce.services.owner import reject
from local_commerce.services.product_images import gallery_urls


def search_filters(search):
    if not isinstance(search, str) or len(search) > 140:
        reject("Search must be at most 140 characters")
    filters = {"status": "Active"}
    if search.strip():
        text = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filters["shop_name"] = ["like", "%" + text + "%"]
    return filters


def discover(search="", address="", start=0):
    from local_commerce.services import customers, orders

    search_filters(search)
    pinned = frappe.get_single("LC Store Settings").get("pinned_shop") or ""
    if address:
        result = customers.nearby(address, start, search, pinned_shop=pinned)
        rows, more = result["shops"], result["has_more"]
    else:
        rows = orders.shops(start, search, pinned_shop=pinned)
        more = len(rows) == 20
    if not rows:
        return {"shops": [], "has_more": more}
    names = [row.name for row in rows]
    metadata = {row.name: row for row in frappe.get_all(
        "LC Shop", filters={"name": ["in", names]},
        fields=["name", "shop_image", "shop_type", "company_currency", "minimum_order_amount",
                "free_delivery_above", "delivery_enabled", "scheduled_enabled"],
    )}
    # Bulk lookup: no request per shop, and no customer/order details are exposed.
    placeholders = ",".join(["%s"] * len(names))
    upcoming = frappe.db.sql(
        f"""select s.shop, s.title, s.ordering_start, s.ordering_end,
            s.delivery_start, s.delivery_end from `tabLC Delivery Slot` s
            where s.shop in ({placeholders}) and s.enabled=1 and coalesce(s.archived,0)=0
            and s.ordering_end > %s and (select count(*) from `tabLC Order` o
                where o.scheduled_slot=s.name and o.status!='Cancelled') < s.capacity
            order by s.delivery_start, s.name""", (*names, now_datetime()), as_dict=True,
    )
    next_slots = {}
    for slot in upcoming:
        next_slots.setdefault(slot.shop, {key: slot[key] for key in (
            "title", "ordering_start", "ordering_end", "delivery_start", "delivery_end"
        )})
    for row in rows:
        extra = metadata[row.name]
        images = gallery_urls(extra.shop_image, [])
        row.update({
            "shop_image": images[0] if images else "",
            "shop_type": extra.shop_type,
            "currency": extra.company_currency or "INR",
            "minimum_order_amount": extra.minimum_order_amount,
            "free_delivery_above": extra.free_delivery_above,
            "normal_delivery": bool(extra.delivery_enabled),
            "next_slot": next_slots.get(row.name) if extra.scheduled_enabled else None,
        })
    return {"shops": rows, "has_more": more, "timezone": frappe.utils.get_system_timezone()}
