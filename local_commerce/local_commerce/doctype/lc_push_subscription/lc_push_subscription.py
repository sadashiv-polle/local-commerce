import frappe
from frappe.model.document import Document

from local_commerce.services.push import _push_operation


class LCPushSubscription(Document):
    def validate(self):
        if not _push_operation.get():
            frappe.throw("Push subscriptions are managed by the app", frappe.PermissionError)

