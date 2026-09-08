"""Install checks and repeatable schema constraints. Never edit ERPNext core."""

import frappe


def before_install():
    import erpnext

    if frappe.__version__.split(".")[0] != "15" or erpnext.__version__.split(".")[0] != "15":
        frappe.throw("Local Commerce requires Frappe 15 and ERPNext 15")
    for name in ("LC Shop", "LC Shop Member"):
        if frappe.db.exists("DocType", name):
            frappe.throw(f"DocType collision: {name}; inspect ownership before installing")
    if frappe.db.exists("Web Page", {"route": "local-commerce"}):
        frappe.throw("Route collision: local-commerce")
    if frappe.db.exists("Module Def", "Local Commerce"):
        frappe.throw("Module collision: Local Commerce")
    from local_commerce.permissions.policy import MEMBER_ROLES, PLATFORM_ROLE

    for role in [PLATFORM_ROLE, *MEMBER_ROLES.values(), "LC Customer"]:
        if frappe.db.exists("Role", role):
            frappe.throw(f"Role collision: {role}; inspect ownership before installing")


def after_install():
    after_migrate()


def after_migrate():
    frappe.db.add_unique("LC Shop Member", ["shop", "user"], "lc_shop_member_unique")
