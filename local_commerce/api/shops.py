import frappe

from local_commerce.services import shops


@frappe.whitelist()
def list_shops(start=0, page_length=20):
    return shops.list_shops(start, page_length)


@frappe.whitelist()
def get_shop(shop):
    return shops.get_shop(shop)


@frappe.whitelist(methods=["POST"])
def update_shop(shop, shop_name, status, description=""):
    return shops.update_shop(shop, shop_name, status, description)
