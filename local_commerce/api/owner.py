import frappe

from local_commerce.services import owner


@frappe.whitelist()
def catalog(shop, start=0, search="", status="All"):
    return owner.catalog(shop, start, search, status)


@frappe.whitelist()
def detail(shop, item):
    return owner.detail(shop, item)


@frappe.whitelist()
def setup_options(shop):
    return owner.setup_options(shop)


@frappe.whitelist(methods=["POST"])
def configure(shop, warehouse, account, cost_center):
    return owner.configure(shop, warehouse, account, cost_center)


@frappe.whitelist(methods=["POST"])
def update_product(
    shop, item, modified, item_name, description="", low_stock=0, sold_out=0, archived=0, price=None
):
    return owner.update_product(
        shop, item, modified, item_name, description, low_stock, sold_out, archived, price
    )


@frappe.whitelist(methods=["POST"])
def adjust_stock(shop, item, action, quantity, reason, request_key, unit_cost=0):
    return owner.adjust_stock(shop, item, action, quantity, reason, request_key, unit_cost)


@frappe.whitelist()
def history(shop, item, start=0):
    return owner.history(shop, item, start)
