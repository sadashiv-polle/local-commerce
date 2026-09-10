import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import customers


@frappe.whitelist(methods=["POST"])
def ensure():
    return customers.ensure_customer()


@frappe.whitelist(methods=["POST"])
def account(start=0):
    return customers.account_info(start)


@frappe.whitelist()
def addresses():
    return customers.list_addresses()


@frappe.whitelist(methods=["POST"])
def save_address(
    name=None,
    address_type="Home",
    address_label="",
    recipient="",
    phone="",
    line1="",
    city="",
    postal_code="",
    latitude=None,
    longitude=None,
    is_default=False,
):
    return customers.save_address(
        name,
        address_type,
        address_label,
        recipient,
        phone,
        line1,
        city,
        postal_code,
        latitude,
        longitude,
        is_default,
    )


@frappe.whitelist(methods=["POST"])
def archive_address(name):
    return customers.archive_address(name)


@frappe.whitelist()
def nearby(address, start=0):
    return customers.nearby(address, start)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=3600)
def signup(email, full_name, redirect_to="/local-commerce#/account"):
    from local_commerce.services.registration import begin

    return begin(email, full_name, redirect_to)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=3600)
def complete_signup(challenge_id, code, password):
    from local_commerce.services.registration import complete

    return complete(challenge_id, code, password)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=3600)
def forgot_password(email):
    from frappe.core.doctype.user.user import reset_password

    reset_password(str(email).strip())
    return {
        "message": "If eligible, this account will receive password reset instructions by email."
    }
