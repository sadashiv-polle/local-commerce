import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import admin


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=240, seconds=3600)
def overview():
    return admin.overview()


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=600, seconds=3600)
def listing(section, search="", shop="", status="", start=0):
    return admin.listing(section, search, shop, status, start)


@frappe.whitelist(methods=["POST"])
def set_accepting(shop, enabled):
    return admin.set_accepting(shop, enabled)


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def setup_options(search=""):
    return admin.setup_options(search)


@frappe.whitelist(methods=["POST"])
def create_shop(shop_name, company="", country="", currency="", gst_registration="Unverified", gst_number="", shop_email=""):
    return admin.create_shop(shop_name, company, country, currency, gst_registration, gst_number, shop_email)


@frappe.whitelist(methods=["POST"])
def save_membership(shop, user, membership_role="Delivery Person", name="", enabled=1):
    return admin.save_membership(shop, user, membership_role, name, enabled)


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=240, seconds=3600)
def attention(category="unpaid", start=0, shop=""):
    from local_commerce.services.operations import attention as get_attention
    return get_attention(category, start, shop)


@frappe.whitelist(methods=["GET"])
def rider_rates():
    from local_commerce.services.operations import rider_rates
    return rider_rates()


@frappe.whitelist(methods=["POST"])
def save_rider_rate(shop, amount):
    from local_commerce.services.operations import rider_rates
    return rider_rates(shop, amount)
