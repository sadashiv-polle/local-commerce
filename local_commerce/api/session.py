import frappe

from local_commerce.services.session import get_context


@frappe.whitelist()
def context():
    return get_context()
