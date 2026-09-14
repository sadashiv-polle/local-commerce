import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import geocoding


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=60, seconds=3600)
def search(query):
    return geocoding.search(query)
