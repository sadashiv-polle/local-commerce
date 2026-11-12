import frappe
from frappe.model.document import Document

class LCMarketplaceOperation(Document):
    def validate(self):
        from local_commerce.services.marketplace import writing
        if not writing.get():
            frappe.throw("Use the marketplace workflow", frappe.PermissionError)
        if self.doctype == "LC Marketplace Event" and not self.is_new():
            frappe.throw("Ledger events are immutable", frappe.PermissionError)

    def on_trash(self):
        frappe.throw("Financial history cannot be deleted", frappe.PermissionError)
