import frappe
from frappe.model.document import Document

from local_commerce.services.customers import _linking_customer


class LCCustomerAccount(Document):
    def validate(self):
        if not _linking_customer.get():
            frappe.throw(
                "Customer account links are managed by the account service", frappe.PermissionError
            )

    def on_trash(self):
        frappe.throw("Customer account links cannot be deleted here", frappe.PermissionError)
