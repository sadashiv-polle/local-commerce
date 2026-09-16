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
def create_shop(shop_name, company="", country="", currency=""):
    return admin.create_shop(shop_name, company, country, currency)


@frappe.whitelist(methods=["POST"])
def save_membership(shop, user, membership_role="Driver", name="", enabled=1):
    return admin.save_membership(shop, user, membership_role, name, enabled)
