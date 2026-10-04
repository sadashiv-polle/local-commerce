"""Email-only reset requests using Frappe's token lifecycle and email queue."""

import re

import frappe

from local_commerce.services.owner import reject

MESSAGE = ("If this email belongs to an eligible account, a reset link will be emailed. "
           "Check your inbox and spam folder.")


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
    link = reset(send_email=False)
    user.send_login_mail(
        "Password Reset",
        "password_reset",
        {"link": link},
        now=False,
        custom_template=frappe.db.get_single_value("System Settings", "reset_password_template"),
    )
