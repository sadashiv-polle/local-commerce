import frappe
from frappe.model.document import Document

from local_commerce.services.customers import _address_operation


class LCCustomerAddress(Document):
    def validate(self):
        if not _address_operation.get():
            frappe.throw("Use the customer address service", frappe.PermissionError)

    def on_trash(self):
        frappe.throw("Customer addresses are archived instead of deleted", frappe.PermissionError)
