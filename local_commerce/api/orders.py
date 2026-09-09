import frappe

from local_commerce.services import orders


@frappe.whitelist()
def shops(start=0):
    return orders.shops(start)


@frappe.whitelist()
def catalog(shop, start=0):
    return orders.catalog(shop, start)


@frappe.whitelist(methods=["POST"])
def place(shop, items, address, request_key):
    return orders.place(shop, items, address, request_key)


@frappe.whitelist()
def list_orders(shop=None, start=0):
    return orders.list_orders(shop, start)


@frappe.whitelist()
def detail(order):
    return orders.detail(order)


@frappe.whitelist(methods=["POST"])
def change(order, target, reason=""):
    return orders.change(order, target, reason)
