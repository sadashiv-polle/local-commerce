import frappe
from frappe.model.document import Document

from local_commerce.permissions.policy import MEMBER_ROLES
from local_commerce.permissions.scope import require_platform


class LCShopMember(Document):
    def validate(self):
        require_platform()
        if self.user in {"Guest", "Administrator"}:
            frappe.throw("Use a named, enabled user for shop membership")
        if not frappe.db.get_value("User", self.user, "enabled"):
            frappe.throw("Membership requires an enabled user")
        role = MEMBER_ROLES.get(self.membership_role)
        if not role or role not in frappe.get_roles(self.user):
            frappe.throw("Assign the matching LC role to this user before adding membership")
        if frappe.db.exists(
            "LC Shop Member", {"shop": self.shop, "user": self.user, "name": ["!=", self.name]}
        ):
            frappe.throw("This user already has a membership in this shop")

    def on_trash(self):
        require_platform()
