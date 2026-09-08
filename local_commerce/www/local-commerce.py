import json
from pathlib import Path

import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/local-commerce"
        raise frappe.Redirect
    manifest_path = Path(
        frappe.get_app_path("local_commerce", "public", "frontend", ".vite", "manifest.json")
    )
    if not manifest_path.exists():
        frappe.throw("Local Commerce assets are missing. Run bench build --app local_commerce.")
    entry = json.loads(manifest_path.read_text())["src/main.js"]
    base = "/assets/local_commerce/frontend/"
    context.lc_entry = base + entry["file"]
    context.lc_css = [base + file for file in entry.get("css", [])]
    context.no_cache = 1
