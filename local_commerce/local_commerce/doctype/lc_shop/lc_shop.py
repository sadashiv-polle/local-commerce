import frappe
from frappe.model.document import Document

from local_commerce.permissions.policy import is_platform
from local_commerce.permissions.scope import identity, require_shop
from local_commerce.services.shop_hours import normalize


class LCShop(Document):
    def __setup__(self):
        # Blank Company requests a new company; insertion defaults run before before_insert.
        self.dont_update_if_missing = ["company", "selling_price_list"]

    def before_insert(self):
        # Frappe can seed this read-only link from global/user defaults.
        # Only inventory setup may assign a dedicated shop price list.
        self.selling_price_list = None
        if self.company:
            return
        from local_commerce.services.business_structure import create_vendor_company
        create_vendor_company(self)

    def validate(self):

        if self.get("order_acceptance") not in (None, "", "Manual", "Automatic"):
            frappe.throw("Choose Manual or Automatic order acceptance")
        user, roles = identity()
        if not is_platform(user, roles):
            require_shop(self.name, "write")
            previous = self.get_doc_before_save()
            if not previous or previous.company != self.company:
                frappe.throw(
                    "Only platform administrators can change Company", frappe.PermissionError
                )
            if previous.get("rider_delivery_fee") != self.get("rider_delivery_fee"):
                frappe.throw("Only platform administrators can change rider earnings rates", frappe.PermissionError)
            payment_fields = [field.fieldname for field in self.meta.fields
                              if field.fieldname.startswith(("cod_", "upi_", "cashfree_"))]
            if "LC Shop Settings Manager" not in roles and any(
                previous.get(field) != self.get(field) for field in payment_fields
            ):
                frappe.throw("Only platform administrators can change payment settings",
                             frappe.PermissionError)
            pricing_fields = (
                "order_acceptance",
                "delivery_enabled",
                "scheduled_enabled",
                "shop_type",
                "fish_wastage_account",
                "minimum_order_amount",
                "free_delivery_above",
                "delivery_fee",
                "delivery_fee_per_km",
                "delivery_included_km",
            )
            if "LC Shop Settings Manager" not in roles and any(
                previous.get(field) != self.get(field) for field in pricing_fields
            ):
                frappe.throw(
                    "Only platform administrators can change shop type, accounts "
                    "or delivery pricing",
                    frappe.PermissionError,
                )
            location_fields = (
                "location_map",
                "address_line1",
                "city",
                "postal_code",
                "latitude",
                "longitude",
                "service_radius_km",
                "live_tracking_enabled",
            )
            if "LC Shop Settings Manager" not in roles and any(
                previous.get(field) != self.get(field) for field in location_fields
            ):
                frappe.throw(
                    "Only platform administrators can change shop location settings",
                    frappe.PermissionError,
                )
        from local_commerce.services.business_structure import validate_shop_structure
        validate_shop_structure(self)
        email = str(self.get("shop_email") or "").strip()
        if email:
            if any(char.isspace() or char in ",;" for char in email):
                frappe.throw("Enter one valid shop email address")
            frappe.utils.validate_email_address(email, throw=True)
        self.shop_email = email

        from local_commerce.services.shop_map import synchronize

        try:
            synchronize(self)
        except ValueError as exc:
            frappe.throw(str(exc))
        if not frappe.db.exists("Company", self.company):
            frappe.throw("A valid ERPNext Company is required")
        self.shop_name = (self.shop_name or "").strip()
        if not self.shop_name:
            frappe.throw("Shop name is required")
        try:
            schedule = normalize(self.opening_hours_json)
        except (TypeError, ValueError) as exc:
            frappe.throw(str(exc))
        self.opening_hours_json = frappe.as_json(schedule) if schedule else ""

    def on_update(self):
        if frappe.db.has_column("LC Shop Member", "shop_name"):
            frappe.db.sql(
                """update `tabLC Shop Member`
                set shop_name=%s
                where shop=%s and coalesce(shop_name, '')!=%s""",
                (self.shop_name, self.name, self.shop_name),
            )
