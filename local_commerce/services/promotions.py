"""Admin-managed homepage artwork, stored in existing store settings."""
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services.promotion_rules import normalize


def validate(doc):
    try:
        config = normalize(frappe.parse_json(doc.get("promotions_json") or "{}"))
    except (ValueError, TypeError):
        frappe.throw("Check the promotional slider settings: use uploaded images, slide titles and a 3–30 second interval.")
    doc.promotions_json = frappe.as_json(config)


def get(admin=False):
    if admin:
        require_platform()
    config = normalize(frappe.parse_json(frappe.get_single("LC Store Settings").get("promotions_json") or "{}"))
    if not admin:
        config["slides"] = [row for row in config["slides"] if row["enabled"] and config["enabled"]]
    return config


def save(config):
    require_platform()
    try:
        config = normalize(frappe.parse_json(config) if isinstance(config, str) else config)
    except ValueError as exc:
        frappe.throw(str(exc))
    doc = frappe.get_single("LC Store Settings")
    doc.promotions_json = frappe.as_json(config)
    doc.save()
    return get(admin=True)
