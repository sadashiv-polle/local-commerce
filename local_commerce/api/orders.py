import frappe

from local_commerce.services import orders


@frappe.whitelist(allow_guest=True, methods=["GET"])
def shops(start=0):
    return orders.shops(start)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def catalog(shop, start=0):
    return orders.catalog(shop, start)


@frappe.whitelist(methods=["POST"])
def place(shop, items, address, request_key, payment_method="Cash on Delivery"):
    return orders.place(shop, items, address, request_key, payment_method)


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


@frappe.whitelist()
def payment_options(shop):
    return orders.payment_options(shop)


@frappe.whitelist(methods=["POST"])
def configure_cod(shop, enabled, cash_account="", mode_of_payment=""):
    return orders.configure_cod(shop, enabled, cash_account, mode_of_payment)


@frappe.whitelist(methods=["POST"])
def assign_driver(order, delivery_user):
    return orders.assign_driver(order, delivery_user)


@frappe.whitelist()
def delivery_profile():
    return orders.delivery_profile()


@frappe.whitelist()
def delivery_assignments(start=0, view="active"):
    return orders.delivery_assignments(start, view)


@frappe.whitelist(methods=["POST"])
def delivery_change(order, target, collected_amount=None, note=""):
    return orders.delivery_change(order, target, collected_amount, note)


@frappe.whitelist()
def cod_collections(shop, view="pending", start=0):
    return orders.cod_collections(shop, view, start)


@frappe.whitelist(methods=["POST"])
def reconcile_cod(collection, owner_note=""):
    return orders.reconcile_cod(collection, owner_note)
