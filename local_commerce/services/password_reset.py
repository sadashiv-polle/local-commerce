"""Email-only reset requests using Frappe's token lifecycle and email queue."""

import re
from urllib.parse import parse_qs, urlencode, urlsplit

import frappe

from local_commerce.services.owner import reject

MESSAGE = (
    "If this email belongs to an eligible account, a reset link will be emailed. "
    "Check your inbox and spam folder."
)


def request(email):
    if not isinstance(email, str):
        reject("Enter your registered email address")
    email = email.strip().lower()
    if len(email) > 140 or not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", email):
        reject("Enter your registered email address, not your username")
    # Queue every valid request: response and timing do not reveal account existence.
    frappe.enqueue(
        "local_commerce.services.password_reset.send",
        email=email,
        queue="short",
        enqueue_after_commit=True,
    )
    return {"message": MESSAGE}


def app_link(native_link):
    from frappe.utils import get_url

    base = get_url(allow_header_override=False).rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or "." not in parsed.hostname:
        raise ValueError("Set host_name to the public HTTPS domain before sending password resets")
    key = parse_qs(urlsplit(native_link).query).get("key", [""])[0]
    if not key:
        raise ValueError("Password reset token was not generated")
    return base + "/local-commerce#/reset-password?" + urlencode({"key": key})


def send(email):
    name = frappe.db.get_value("User", {"email": email, "enabled": 1}, "name")
    if not name or name in {"Administrator", "Guest"}:
        return
    user = frappe.get_doc("User", name)
    if not user.enabled or user.email.lower() != email:
        return
    # Frappe v15 releases expose either reset_password or _reset_password.
    validator = getattr(user, "validate_reset_password", None)
    if callable(validator):
        validator()
    reset = getattr(user, "_reset_password", None) or user.reset_password
    link = app_link(reset(send_email=False))
    user.send_login_mail(
        "Password Reset",
        "password_reset",
        {"link": link},
        now=True,
        custom_template=frappe.db.get_single_value("System Settings", "reset_password_template"),
    )


def complete(key, new_password):
    from frappe.core.doctype.user.user import update_password

    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,128}", key):
        reject("This reset link is invalid. Request a new link.")
    if not isinstance(new_password, str) or not 8 <= len(new_password) <= 1000:
        reject("Use a password between 8 and 1000 characters.")
    try:
        update_password(new_password=new_password, key=key, logout_all_sessions=1)
    except frappe.ValidationError:
        reject(
            "The password could not be changed. Choose a stronger password or request a new link."
        )
    if frappe.local.response.get("http_status_code") == 410:
        reject("This reset link has expired or was already used. Request a new link.")
    return {"updated": True}
