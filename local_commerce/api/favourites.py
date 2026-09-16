import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import orders
from local_commerce.services.owner import reject


def user():
    if frappe.session.user == "Guest":
        frappe.throw("Sign in to save favourites", frappe.PermissionError)
    return frappe.session.user


@frappe.whitelist(methods=["GET"])
def ids():
    return frappe.get_all(
        "LC Favourite", filters={"user": user()}, pluck="item", limit_page_length=0
    )


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=300, seconds=3600)
def toggle(shop, item, saved=1):
    account = user()
    if str(saved) not in ("0", "1"):
        reject("Invalid favourite selection")
    frappe.db.sql("select name from `tabUser` where name=%s for update", (account,))
    existing = frappe.db.get_value("LC Favourite", {"user": account, "item": item}, "name")
    if str(saved) == "0":
        if existing:
            frappe.delete_doc("LC Favourite", existing, ignore_permissions=True)
        return {"saved": False}
    product = orders.public_product(shop, item)
    if not existing:
        if frappe.db.count("LC Favourite", {"user": account}) >= 200:
            reject("You can save up to 200 favourites. Remove one before adding another")
        frappe.get_doc(
            {
                "doctype": "LC Favourite",
                "user": account,
                "item": item,
                "shop": shop,
                "item_name": product["item_name"],
            }
        ).insert(ignore_permissions=True)
    return {"saved": True}


@frappe.whitelist(methods=["GET"])
def list_items():
    rows = frappe.get_all(
        "LC Favourite",
        filters={"user": user()},
        fields=["item", "item_name", "shop"],
        order_by="creation desc",
        limit_page_length=0,
    )
    result = []
    for row in rows:
        fallback = {
            "item": row.item,
            "item_name": row.item_name,
            "shop": row.shop,
            "shop_name": "Shop unavailable",
            "available": 0,
            "rate": None,
            "image": "",
            "unavailable": True,
        }
        active = frappe.db.get_value("LC Shop", {"name": row.shop, "status": "Active"}, "shop_name")
        if not active or not frappe.db.exists("Item", row.item):
            result.append(fallback)
            continue
        item = frappe.get_doc("Item", row.item)
        if (
            item.lc_shop != row.shop
            or item.disabled
            or not item.is_stock_item
            or item.has_variants
            or item.variant_of
            or item.has_batch_no
            or item.has_serial_no
        ):
            result.append({**fallback, "shop_name": active})
            continue
        result.append(
            {
                **orders.public_product(row.shop, row.item),
                "shop": row.shop,
                "shop_name": active,
                "unavailable": False,
            }
        )
    return result
