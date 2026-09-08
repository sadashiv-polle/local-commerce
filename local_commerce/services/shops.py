import frappe

from local_commerce.permissions.scope import require_shop


def list_shops(start=0, page_length=20):
    start, page_length = int(start), int(page_length)
    if start < 0 or not 1 <= page_length <= 100:
        frappe.throw("Invalid pagination")
    return frappe.get_list(
        "LC Shop",
        fields=["name", "shop_name", "company", "status"],
        start=start,
        page_length=page_length,
        order_by="shop_name asc, name asc",
    )


def get_shop(shop):
    require_shop(shop)
    doc = frappe.get_doc("LC Shop", shop)
    doc.check_permission("read")
    return {key: doc.get(key) for key in ("name", "shop_name", "company", "status", "description")}


def update_shop(shop, shop_name, status, description=""):
    require_shop(shop, "write")
    doc = frappe.get_doc("LC Shop", shop)
    doc.shop_name, doc.status, doc.description = shop_name, status, description
    doc.save()
    return get_shop(shop)
