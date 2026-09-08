import frappe
from frappe.model.document import Document

from local_commerce.permissions.policy import is_platform
from local_commerce.permissions.scope import identity, require_shop


class LCShop(Document):
    def validate(self):
        user, roles = identity()
        if not is_platform(user, roles):
            require_shop(self.name, "write")
            previous = self.get_doc_before_save()
            if not previous or previous.company != self.company:
                frappe.throw(
                    "Only platform administrators can change Company", frappe.PermissionError
                )
        if not frappe.db.exists("Company", self.company):
            frappe.throw("A valid ERPNext Company is required")
        self.shop_name = (self.shop_name or "").strip()
        if not self.shop_name:
            frappe.throw("Shop name is required")
