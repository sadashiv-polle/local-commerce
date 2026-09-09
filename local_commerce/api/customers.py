import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import validate_email_address

from local_commerce.services import customers
from local_commerce.services.owner import reject


@frappe.whitelist(methods=["POST"])
def ensure():
    return customers.ensure_customer()


@frappe.whitelist(methods=["POST"])
def account(start=0):
    return customers.account_info(start)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=3600)
def signup(email, full_name, redirect_to="/local-commerce#/account"):
    from frappe.core.doctype.user.user import sign_up

    email = validate_email_address(str(email).strip().lower(), throw=True)
    full_name = str(full_name).strip()
    if not full_name or len(full_name) > 140:
        reject("Enter your full name (up to 140 characters)")
    if not isinstance(redirect_to, str) or not redirect_to.startswith("/local-commerce#/"):
        redirect_to = "/local-commerce#/account"
    if len(redirect_to) > 500 or any(c in redirect_to for c in ("\n", "\r", "\\")):
        reject("Invalid return address")
    result = sign_up(email, full_name, redirect_to)
    if result[0] == 2:
        reject(
            "Signup email is unavailable. Please contact the store to configure verification email."
        )
    # Do not reveal whether an address is already registered or disabled.
    return {
        "message": (
            "Check your email to verify your new account and set a password. "
            "Already registered? Use Login or Forgot Password."
        )
    }
