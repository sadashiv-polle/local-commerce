import frappe
from frappe.model.document import Document

from local_commerce.permissions.policy import is_platform
from local_commerce.permissions.scope import identity, require_shop


class LCShop(Document):
    def before_insert(self):
        # Frappe can seed this read-only link from global/user defaults.
        # Only inventory setup may assign a dedicated shop price list.
        self.selling_price_list = None
        if self.company:
            return
        user, roles = identity()
        if not is_platform(user, roles):
            frappe.throw("Only platform administrators can create shops", frappe.PermissionError)
        self.shop_name = (self.shop_name or "").strip()
        if not self.shop_name:
            frappe.throw("Shop name is required")
        if frappe.db.exists("Company", self.shop_name):
            frappe.throw(
                "A Company with this Shop Name already exists. Select it explicitly in Company "
                "if it belongs to this shop, or use a different Shop Name."
            )
        country = self.company_country or frappe.db.get_single_value("Global Defaults", "country")
        currency = self.company_currency or frappe.db.get_single_value(
            "Global Defaults", "default_currency"
        )
        if not country or not currency:
            frappe.throw("Select New Company Country and New Company Currency before saving")
        # A unique abbreviation avoids collisions between shops with the same initials.
        abbr = "LC" + frappe.generate_hash(length=8).upper()
        while frappe.db.exists("Company", {"abbr": abbr}):
            abbr = "LC" + frappe.generate_hash(length=8).upper()
        company = frappe.get_doc(
            {
                "doctype": "Company",
                "company_name": self.shop_name,
                "abbr": abbr,
                "country": country,
                "default_currency": currency,
                "create_chart_of_accounts_based_on": "Standard Template",
                "chart_of_accounts": "Standard",
            }
        )
        # Scoped elevation after platform authorization; normal ERP validations still run.
        # No commit: Company and Shop are saved in the same request transaction.
        company.insert(ignore_permissions=True)
        self.company = company.name

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
