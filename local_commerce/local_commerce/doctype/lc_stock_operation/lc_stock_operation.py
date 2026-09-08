import frappe
from frappe.model.document import Document

from local_commerce.services.owner import _owner_operation


class LCStockOperation(Document):
    def validate(self):
        if not _owner_operation.get():
            frappe.throw(
                "Stock operations are recorded by the stock service", frappe.PermissionError
            )

    def on_trash(self):
        frappe.throw("Stock operation history cannot be deleted", frappe.PermissionError)
