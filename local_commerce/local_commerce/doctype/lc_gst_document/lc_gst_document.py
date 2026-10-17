import frappe
from frappe.model.document import Document
from local_commerce.services.gst.accounting import writing

class LCGSTDocument(Document):
    def validate(self):
        if not writing.get() or not self.is_new():
            frappe.throw("GST documents are immutable; use a credit note", frappe.PermissionError)
    def on_trash(self):
        frappe.throw("GST documents cannot be deleted", frappe.PermissionError)
    def before_rename(self, *args):
        frappe.throw("GST documents cannot be renamed", frappe.PermissionError)
