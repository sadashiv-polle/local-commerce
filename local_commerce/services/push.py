"""Standards-based Web Push subscriptions and delivery."""

import base64
import hashlib
import json
from contextvars import ContextVar
from pathlib import Path

import frappe
from frappe.utils import now_datetime

from local_commerce.services.owner import reject

_push_operation = ContextVar("lc_push_operation", default=False)


def _user():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Please sign in to manage notifications", frappe.AuthenticationError)
    return user


def _private_key_path():
    configured = frappe.conf.get("lc_web_push_private_key")
    if not configured:
        return None
    path = Path(configured)
    if not path.is_absolute():
        path = Path(frappe.get_site_path()) / path
    return path


def _public_key():
    path = _private_key_path()
    if not path or not path.is_file():
        return ""
    from cryptography.hazmat.primitives import serialization

    private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    numbers = private_key.public_key().public_numbers()
    raw = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def status(endpoint=""):
    user = _user()
    public_key = _public_key()
    endpoints = frappe.get_all(
        "LC Push Subscription",
        filters={"user": user, "enabled": 1},
        pluck="endpoint_hash",
        limit_page_length=0,
    )
    endpoint_hash = hashlib.sha256(str(endpoint).encode()).hexdigest() if endpoint else ""
    subscribed = bool(endpoint_hash and frappe.db.exists(
        "LC Push Subscription", {"user": user, "endpoint_hash": endpoint_hash, "enabled": 1}
    ))
    return {"configured": bool(public_key), "public_key": public_key,
            "devices": len(endpoints), "subscribed": subscribed}


def _payload(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            reject("Invalid push subscription")
    if not isinstance(value, dict):
        reject("Invalid push subscription")
    keys = value.get("keys") or {}
    endpoint = str(value.get("endpoint") or "").strip()
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not endpoint.startswith("https://") or not p256dh or not auth:
        reject("Invalid push subscription")
    if len(endpoint) > 2000 or len(p256dh) > 500 or len(auth) > 500:
        reject("Invalid push subscription")
    return endpoint, p256dh, auth


def subscribe(subscription):
    user = _user()
    if not _public_key():
        reject("Phone notifications are not configured yet")
    endpoint, p256dh, auth = _payload(subscription)
    endpoint_hash = hashlib.sha256(endpoint.encode()).hexdigest()
    existing = frappe.db.get_value("LC Push Subscription", {"endpoint_hash": endpoint_hash}, "name")
    token = _push_operation.set(True)
    try:
        doc = (
            frappe.get_doc("LC Push Subscription", existing)
            if existing
            else frappe.new_doc("LC Push Subscription")
        )
        doc.update(
            {
                "user": user,
                "endpoint_hash": endpoint_hash,
                "endpoint": endpoint,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": (frappe.get_request_header("User-Agent") or "")[:500],
                "enabled": 1,
            }
        )
        doc.save(ignore_permissions=True)
    finally:
        _push_operation.reset(token)
    return {"subscribed": True}


def unsubscribe(endpoint):
    user = _user()
    endpoint_hash = hashlib.sha256(str(endpoint).encode()).hexdigest()
    name = frappe.db.get_value(
        "LC Push Subscription", {"endpoint_hash": endpoint_hash, "user": user}, "name"
    )
    if name:
        frappe.db.set_value("LC Push Subscription", name, "enabled", 0, update_modified=False)
    return {"subscribed": False}


def send_notification(notification):
    row = frappe.db.get_value(
        "LC Notification",
        notification,
        ["recipient_user", "title", "message", "target"],
        as_dict=True,
    )
    private_key = _private_key_path()
    if not row or not private_key or not private_key.is_file():
        return
    from pywebpush import WebPushException, webpush

    subscriptions = frappe.get_all(
        "LC Push Subscription",
        filters={"user": row.recipient_user, "enabled": 1},
        fields=["name", "endpoint", "p256dh"],
        limit_page_length=0,
    )
    payload = json.dumps(
        {
            "title": row.title,
            "body": row.message,
            "url": f"/local-commerce#{row.target}",
            "tag": f"lc-{notification}",
        }
    )
    subject = frappe.conf.get("lc_web_push_subject") or "mailto:admin@localhost"
    for subscription in subscriptions:
        try:
            auth = frappe.get_doc("LC Push Subscription", subscription.name).get_password("auth")
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": auth},
                },
                data=payload,
                vapid_private_key=str(private_key),
                vapid_claims={"sub": subject},
                ttl=86400,
            )
            frappe.db.set_value(
                "LC Push Subscription",
                subscription.name,
                "last_success_at",
                now_datetime(),
                update_modified=False,
            )
        except WebPushException as error:
            status_code = getattr(getattr(error, "response", None), "status_code", 0)
            if status_code in (404, 410):
                frappe.db.set_value(
                    "LC Push Subscription",
                    subscription.name,
                    "enabled",
                    0,
                    update_modified=False,
                )
            else:
                frappe.log_error(title="Local Commerce push delivery failed", message=str(error))
