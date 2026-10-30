import frappe
from frappe.model.document import Document
from local_commerce.services.campaigns import _operation


class LCPromotionPreference(Document):
    def validate(self):
        if not _operation.get():
            frappe.throw("Use the campaign settings in the app", frappe.PermissionError)
