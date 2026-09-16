import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import storefront


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def featured():
    return storefront.featured()


@frappe.whitelist(methods=["GET"])
def settings():
    return storefront.settings()


@frappe.whitelist(methods=["POST"])
def configure(mode, title="Picked for you", random_count=6, products=None):
    return storefront.configure(mode, title, random_count, products)


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def product_options(search="", start=0):
    return storefront.product_options(search, start)
