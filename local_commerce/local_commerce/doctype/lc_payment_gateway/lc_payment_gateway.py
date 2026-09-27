import frappe
from frappe.model.document import Document

from local_commerce.permissions.scope import require_platform


class LCPaymentGateway(Document):
    def validate(self):
        require_platform()
        if self.environment not in {"sandbox", "production"}:
            frappe.throw("Select Sandbox or Production")
        if not self.client_id or not self.get_password("client_secret", raise_exception=False):
            frappe.throw("Enter the Cashfree Client ID and Secret")
        old = self.get_doc_before_save()
        if old and (old.environment != self.environment or old.client_id != self.client_id):
            frappe.throw("Create a new gateway profile when changing environment or merchant ID")

    def on_trash(self):
        if frappe.db.exists("LC Order", {"gateway_profile": self.name}):
            frappe.throw("This gateway has payment history. Disable it instead")
