import frappe
from frappe.model.document import Document

from local_commerce.services.orders import _order_operation


class LCCODCollection(Document):
    def validate(self):
        if not _order_operation.get():
            frappe.throw("Use the Cash on Delivery workflow", frappe.PermissionError)

    def on_trash(self):
        frappe.throw("Cash collection history cannot be deleted", frappe.PermissionError)
