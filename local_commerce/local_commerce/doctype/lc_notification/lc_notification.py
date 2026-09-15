import frappe
from frappe.model.document import Document

from local_commerce.services.notifications import _notification_operation


class LCNotification(Document):
    def validate(self):
        if not _notification_operation.get():
            frappe.throw("Notifications are created by order activity", frappe.PermissionError)
