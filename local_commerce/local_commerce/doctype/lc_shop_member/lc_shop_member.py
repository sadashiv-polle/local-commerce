import frappe
from frappe.model.document import Document

from local_commerce.permissions.policy import MEMBER_ROLES
from local_commerce.permissions.scope import require_platform


class LCShopMember(Document):
    def validate(self):
        require_platform()
        self.shop_name = frappe.db.get_value("LC Shop", self.shop, "shop_name")
        if not self.shop_name:
            frappe.throw("Membership requires a valid shop")
        if self.user in {"Guest", "Administrator"}:
            frappe.throw("Use a named, enabled user for shop membership")
        if not frappe.db.get_value("User", self.user, "enabled"):
            frappe.throw("Membership requires an enabled user")
        role = MEMBER_ROLES.get(self.membership_role)
        if not role:
            frappe.throw("Select a valid membership role")
        if frappe.db.exists(
            "LC Shop Member", {"shop": self.shop, "user": self.user, "name": ["!=", self.name]}
        ):
            frappe.throw("This user already has a membership in this shop")
        if role not in frappe.get_roles(self.user):
            # Platform access was verified above. Keep authentication roles and shop
            # membership in the same transaction so administrators cannot create a
            # membership that is unusable until a separate User edit is performed.
            user = frappe.get_doc("User", self.user)
            user.append("roles", {"role": role})
            user.save(ignore_permissions=True)

    def on_trash(self):
        require_platform()
