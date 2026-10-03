import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import stock_alerts


@frappe.whitelist(methods=['GET'])
def ids():
    return stock_alerts.ids()


@frappe.whitelist(methods=['POST'])
@rate_limit(limit=300, seconds=3600)
def toggle(shop, item, saved=1):
    return stock_alerts.toggle(shop, item, saved)
