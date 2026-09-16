"""Personal storefront suggestions, scoped exclusively to the authenticated account."""

import frappe
from frappe.utils import add_days, getdate, nowdate

from local_commerce.services.location_rules import distance_km, point
from local_commerce.services.orders import public_product
from local_commerce.services.recommendation_rules import rank_products


def suggestions(address=""):
    empty = {"name": "customer-picks", "title": "Your everyday picks", "items": []}
    user = frappe.session.user
    if user == "Guest" or "LC Customer" not in frappe.get_roles(user):
        return empty
    destination = None
    if address:
        saved = frappe.db.get_value(
            "LC Customer Address",
            {"name": address, "user": user, "disabled": 0},
            ["latitude", "longitude"],
            as_dict=True,
        )
        if not saved:
            frappe.throw("Address access denied", frappe.PermissionError)
        destination = point(saved.latitude, saved.longitude)
    today = getdate(nowdate())
    # Bounded recent completed orders; abandoned/cancelled carts do not influence picks.
    purchases = frappe.db.sql(
        """select o.name as `order`, o.creation as purchased_on, i.item_code as item
        from (select name, creation, sales_order from `tabLC Order`
            where customer_user=%s and status='Delivered' and creation >= %s
            order by creation desc limit 200) o
        inner join `tabSales Order Item` i on i.parent=o.sales_order
            and i.parenttype='Sales Order' and i.parentfield='items'
        order by o.creation desc, i.idx asc limit 4800""",
        (user, add_days(today, -180)),
        as_dict=True,
    )
    for row in purchases:
        row.purchased_on = getdate(row.purchased_on)
    result = []
    for name in rank_products(purchases, today)[:60]:
        item = frappe.db.get_value("Item", name, ["lc_shop", "disabled"], as_dict=True)
        if not item or item.disabled or not item.lc_shop:
            continue
        shop = frappe.db.get_value(
            "LC Shop", {"name": item.lc_shop, "status": "Active"},
            ["shop_name", "latitude", "longitude", "service_radius_km", "delivery_enabled"],
            as_dict=True,
        )
        if not shop:
            continue
        if destination:
            origin = point(shop.latitude, shop.longitude)
            if (
                not shop.delivery_enabled
                or not origin
                or distance_km(origin, destination) > float(shop.service_radius_km or 0)
            ):
                continue
        try:
            product = public_product(item.lc_shop, name)
        except (frappe.ValidationError, frappe.DoesNotExistError):
            continue
        if product["rate"] is None or product["available"] <= 0:
            continue
        result.append({**product, "shop": item.lc_shop, "shop_name": shop.shop_name})
        if len(result) == 8:
            break
    return {**empty, "items": result}
