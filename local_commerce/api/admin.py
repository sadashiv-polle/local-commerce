import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import admin


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=240, seconds=3600)
def overview():
    return admin.overview()


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=600, seconds=3600)
def listing(section, search="", shop="", status="", start=0):
    return admin.listing(section, search, shop, status, start)


@frappe.whitelist(methods=["POST"])
def set_accepting(shop, enabled):
    return admin.set_accepting(shop, enabled)


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def setup_options(search=""):
    return admin.setup_options(search)


@frappe.whitelist(methods=["POST"])
def create_shop(shop_name, company="", country="", currency="", gst_registration="Unverified", gst_number="", shop_email="", auto_setup=0, onboarding=None, bank_details=None, business_model="Owned shop", platform_company="", company_name=""):
    from local_commerce.permissions.scope import require_platform
    from frappe.utils import strip_html
    require_platform()
    try:
        return admin.create_shop(shop_name, company, country, currency, gst_registration, gst_number, shop_email, auto_setup, onboarding, bank_details, business_model, platform_company, company_name)
    except frappe.ValidationError as exc:
        # ERPNext validates linked accounts and Company defaults too. Show its
        # validation to the authorized administrator, never a traceback or HTML.
        if not frappe.local.response.get("lc_message"):
            detail = strip_html(str(exc)).strip()[:1800]
            frappe.local.response["lc_message"] = "Shop setup: " + (detail or "ERPNext rejected the shop details. Review Company and account defaults.")
        raise


@frappe.whitelist(methods=["POST"])
def save_membership(shop, user, membership_role="Delivery Person", name="", enabled=1):
    from local_commerce.permissions.scope import require_platform
    from frappe.utils import strip_html
    require_platform()
    try:
        return admin.save_membership(shop, user, membership_role, name, enabled)
    except frappe.ValidationError as exc:
        if not frappe.local.response.get("lc_message"):
            detail = strip_html(str(exc)).strip()[:1800]
            frappe.local.response["lc_message"] = "Team membership: " + (detail or "Review the selected shop, user and role.")
        raise


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=240, seconds=3600)
def attention(category="unpaid", start=0, shop=""):
    from local_commerce.services.operations import attention as get_attention
    return get_attention(category, start, shop)


@frappe.whitelist(methods=["GET"])
def rider_rates():
    from local_commerce.services.operations import rider_rates
    return rider_rates()


@frappe.whitelist(methods=["POST"])
def save_rider_rate(shop, amount):
    from local_commerce.services.operations import rider_rates
    return rider_rates(shop, amount)


@frappe.whitelist(methods=['GET'])
def shop_banks(shop):
    from local_commerce.services.shop_banking import shop_settings
    return shop_settings(shop)


@frappe.whitelist(methods=['POST'])
def save_shop_bank(shop, details, usage='store'):
    from local_commerce.services.shop_banking import save_shop_bank as save
    return save(shop, details, usage)


@frappe.whitelist(methods=["GET"])
def app_icon():
    from local_commerce.permissions.scope import require_platform
    from local_commerce.services.branding import installed_icon
    require_platform()
    return {"icon": installed_icon()}


@frappe.whitelist(methods=["POST"])
def save_app_icon(icon):
    from local_commerce.services.branding import save_installed_icon
    return save_installed_icon(icon)
