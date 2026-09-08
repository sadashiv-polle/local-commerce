import frappe

from local_commerce.services import products


@frappe.whitelist()
def options(shop):
    return products.options(shop)


@frappe.whitelist()
def list_items(shop, start=0):
    return products.list_items(shop, start)


@frappe.whitelist(methods=["POST"])
def create_item(shop, item_name, item_group, stock_uom):
    return products.create_item(shop, item_name, item_group, stock_uom)
