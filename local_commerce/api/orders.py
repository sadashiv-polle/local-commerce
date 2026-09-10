import frappe

from local_commerce.services import orders


@frappe.whitelist(allow_guest=True, methods=["GET"])
def shops(start=0):
    return orders.shops(start)


@frappe.whitelist(allow_guest=True, methods=["GET"])
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


@frappe.whitelist()
def drivers(shop):
    return orders.drivers(shop)


@frappe.whitelist(methods=["POST"])
def assign_driver(order, delivery_user):
    return orders.assign_driver(order, delivery_user)


@frappe.whitelist()
def delivery_assignments(start=0):
    return orders.delivery_assignments(start)


@frappe.whitelist(methods=["POST"])
def delivery_change(order, target):
    return orders.delivery_change(order, target)
