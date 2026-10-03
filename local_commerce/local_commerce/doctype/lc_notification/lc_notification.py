import frappe
from frappe.model.document import Document

from local_commerce.services.notifications import _notification_operation


class LCNotification(Document):
    def validate(self):
        if not _notification_operation.get():
            frappe.throw("Notifications are created by app activity", frappe.PermissionError)
        if not self.order and not self.get("item"):
            frappe.throw("A notification must reference an order or product")
