import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import orders


@frappe.whitelist(allow_guest=True, methods=["GET"])
def shops(start=0):
    return orders.shops(start)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def catalog(shop, start=0, search="", category="", in_stock=0):
    return orders.catalog(shop, start, search, category, in_stock)


@frappe.whitelist(methods=["POST"])
def place(shop, items, address, request_key, payment_method="Cash on Delivery",
          delivery_mode="Normal", scheduled_slot=None):
    return orders.place(
        shop, items, address, request_key, payment_method, delivery_mode, scheduled_slot
    )


@frappe.whitelist(methods=["GET"])
def active_orders():
    return orders.active_orders()


@frappe.whitelist()
def list_orders(shop=None, start=0, status=None, delivery_mode=None):
    return orders.list_orders(shop, start, status, delivery_mode)


@frappe.whitelist()
def detail(order):
    return orders.detail(order)


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=120, seconds=3600)
def delivery_route(order):
    return orders.delivery_route(order)


@frappe.whitelist(methods=["POST"])
def change(order, target, reason=""):
    return orders.change(order, target, reason)


@frappe.whitelist(methods=["POST"])
def finalize_weights(order, modified, weights):
    from local_commerce.services.packing import finalize

    return finalize(order, modified, weights)


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
def delivery_assignments(start=0, view="active", delivery_mode=None):
    return orders.delivery_assignments(start, view, delivery_mode)


@frappe.whitelist(methods=["POST"])
def delivery_change(order, target, collected_amount=None, note="", delivery_otp=""):
    return orders.delivery_change(order, target, collected_amount, note, delivery_otp)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def upload_delivery_proof(order):
    return orders.upload_delivery_proof(order)


@frappe.whitelist(methods=["POST"])
def update_driver_location(order, latitude, longitude, accuracy=None):
    return orders.update_driver_location(order, latitude, longitude, accuracy)


@frappe.whitelist()
def cod_collections(shop, view="pending", start=0):
    return orders.cod_collections(shop, view, start)


@frappe.whitelist(methods=["POST"])
def reconcile_cod(collection, owner_note=""):
    return orders.reconcile_cod(collection, owner_note)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=600, seconds=3600)
def quote(shop, items, latitude=None, longitude=None, delivery_mode="Normal", scheduled_slot=None):
    return orders.quote(shop, items, latitude, longitude, delivery_mode, scheduled_slot)


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=120, seconds=3600)
def reorder_preview(order):
    return orders.reorder_preview(order)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=3600)
def submit_rating(order, shop_rating, product_rating, delivery_rating, comment=""):
    return orders.submit_rating(order, shop_rating, product_rating, delivery_rating, comment)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def search_products(search, start=0, latitude=None, longitude=None, category=""):
    return orders.search_products(search, start, latitude, longitude, category)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def product(shop, item):
    return orders.public_product(shop, item)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=180, seconds=3600)
def map_shops(south, west, north, east):
    from local_commerce.services.shop_map_discovery import shops

    return shops(south, west, north, east)
