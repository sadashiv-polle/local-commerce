"""Email-code verification before creating a password-enabled User."""

import hashlib
import hmac
import secrets
import time

import frappe
from frappe.utils import validate_email_address

from local_commerce.services.owner import reject


def signup_allowed():
    from frappe.core.doctype.user.user import is_signup_disabled

    if is_signup_disabled():
        reject("Signup is disabled. Enable signup in Website Settings.")


def begin(email, full_name, redirect_to):
    signup_allowed()
    email = validate_email_address(str(email).strip().lower(), throw=True)
    full_name = str(full_name).strip()
    if not full_name or len(full_name) > 140:
        reject("Enter a full name up to 140 characters")
    token = secrets.token_urlsafe(32)
    code = str(secrets.randbelow(1000000)).zfill(6)
    key = "lc-signup:" + token
    frappe.cache.set_value(
        key,
        {
            "email": email,
            "full_name": full_name,
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            "expires": time.time() + 600,
            "attempts": 0,
        },
        expires_in_sec=600,
    )
    try:
        frappe.sendmail(
            recipients=[email],
            subject="Your Local Commerce verification code",
            message=f"Your verification code is <strong>{code}</strong>. It expires in 10 minutes. "
            "If you did not request an account, ignore this email.",
            now=True,
        )
    except Exception:
        frappe.cache.delete_value(key)
        reject("Verification email could not be sent. Configure a default outgoing Email Account.")
    return {"challenge_id": token, "message": "Enter the six-digit code sent to your email."}


def complete(challenge_id, code, password):
    signup_allowed()
    if not isinstance(challenge_id, str) or not 20 <= len(challenge_id) <= 100:
        reject("Invalid verification request")
    if not isinstance(password, str) or not 8 <= len(password) <= 1000:
        reject("Choose a password between 8 and 1000 characters")
    key = "lc-signup:" + challenge_id
    with frappe.cache.lock("lc-signup-lock:" + challenge_id, timeout=60, blocking_timeout=5):
        data = frappe.cache.get_value(key)
        if not data or data["expires"] < time.time() or data["attempts"] >= 5:
            reject("Verification expired. Request a new code.")
        data["attempts"] += 1
        frappe.cache.set_value(key, data, expires_in_sec=max(1, int(data["expires"] - time.time())))
        if not hmac.compare_digest(
            hashlib.sha256(str(code).strip().encode()).hexdigest(), data["code_hash"]
        ):
            reject("Incorrect verification code")
        if frappe.db.exists("User", data["email"]):
            frappe.cache.delete_value(key)
            reject("This account already exists. Use Login or Forgot password.")
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": data["email"],
                "first_name": data["full_name"],
                "enabled": 1,
                "user_type": "Website User",
                "send_welcome_email": 0,
                "new_password": password,
                "roles": [{"role": "LC Customer"}],
            }
        ).insert(ignore_permissions=True)
        from local_commerce.services.customers import ensure_customer

        previous = frappe.session.user
        try:
            frappe.set_user(user.name)
            ensure_customer()
        finally:
            frappe.set_user(previous)
        frappe.local.login_manager.login_as(user.name)
        frappe.cache.delete_value(key)
        return {"authenticated": True}
