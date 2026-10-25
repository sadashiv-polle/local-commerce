import frappe
from frappe.rate_limiter import rate_limit
from local_commerce.services import social_login


@frappe.whitelist(allow_guest=True, methods=['GET'])
def options():
    return {'google': social_login.google_enabled()}


@frappe.whitelist(allow_guest=True, methods=['POST'])
@rate_limit(limit=15, seconds=300)
def google(next_page=None):
    return social_login.google_authorize(next_page)
