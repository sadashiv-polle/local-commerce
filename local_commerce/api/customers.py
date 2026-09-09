import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import customers


@frappe.whitelist(methods=["POST"])
def ensure():
    return customers.ensure_customer()


@frappe.whitelist(methods=["POST"])
def account(start=0):
    return customers.account_info(start)


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
