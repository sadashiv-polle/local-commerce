"""Narrow owner product API; ERPNext remains the Item master."""

from contextvars import ContextVar

import frappe

from local_commerce.permissions.policy import is_platform
from local_commerce.permissions.scope import identity, memberships, require_shop

_item_creation = ContextVar("lc_item_creation", default=False)


def tenant_user(user=None):
    user, roles = identity(user)
    return user, roles, not is_platform(user, roles) and any(r.startswith("LC ") for r in roles)


def item_permission(doc, user=None, permission_type=None, **kwargs):
    user, roles, tenant = tenant_user(user)
    if not tenant:
        return None
    if permission_type not in (None, "read", "select"):
        return False
    from local_commerce.permissions.policy import can_access_shop

    return can_access_shop(user, roles, memberships(user), doc.get("lc_shop"))


def item_query(user=None):
    user, roles, tenant = tenant_user(user)
    if not tenant:
        return ""
    from local_commerce.permissions.policy import can_access_shop

    rows = memberships(user)
    shops = sorted({m.shop for m in rows if can_access_shop(user, roles, rows, m.shop)})
    if not shops:
        return "1=0"
    return "`tabItem`.`lc_shop` in (" + ",".join(frappe.db.escape(s) for s in shops) + ")"


def validate_item(doc, method=None):
    previous = doc.get_doc_before_save()
    if previous and previous.get("lc_shop") != doc.get("lc_shop"):
        frappe.throw("Item shop ownership cannot be changed", frappe.PermissionError)
    if doc.is_new() and doc.get("lc_shop") and not _item_creation.get():
        frappe.throw(
            "Create shop items through the Local Commerce workspace", frappe.PermissionError
        )
    if tenant_user()[2] and not _item_creation.get():
        frappe.throw("Use the Local Commerce product API", frappe.PermissionError)


def protect_item(doc, method=None, *args, **kwargs):
    if doc.get("lc_shop") or tenant_user()[2]:
        frappe.throw("Shop items cannot be deleted or renamed here", frappe.PermissionError)


def options(shop):
    require_shop(shop, "write")
    # Shared taxonomy only. These queries never return Item or financial records.
    return {
        "groups": frappe.get_all(
            "Item Group",
            filters={"is_group": 0},
            pluck="name",
            order_by="name",
            limit_page_length=500,
        ),
        "uoms": frappe.get_all(
            "UOM", filters={"enabled": 1}, pluck="name", order_by="name", limit_page_length=500
        ),
    }


def list_items(shop, start=0):
    require_shop(shop)
    start = int(start)
    if start < 0:
        frappe.throw("Invalid pagination")
    # Explicit scope after authorization; LC users receive no broad ERPNext role.
    return frappe.get_all(
        "Item",
        filters={"lc_shop": shop},
        fields=["name", "item_name", "item_group", "stock_uom", "disabled"],
        start=start,
        limit_page_length=20,
        order_by="creation desc, name desc",
    )


def create_item(shop, item_name, item_group, stock_uom):
    require_shop(shop, "write")
    shop_doc = frappe.get_doc("LC Shop", shop)
    if shop_doc.status == "Disabled":
        frappe.throw("This shop is disabled")
    if not isinstance(item_name, str) or not 1 <= len(item_name.strip()) <= 140:
        frappe.throw("Item name must contain 1 to 140 characters")
    if not isinstance(item_group, str) or not isinstance(stock_uom, str):
        frappe.throw("Category and unit must be names")
    if not frappe.db.exists("Item Group", {"name": item_group, "is_group": 0}):
        frappe.throw("Select a valid item group")
    if not frappe.db.exists("UOM", {"name": stock_uom, "enabled": 1}):
        frappe.throw("Select an enabled unit of measure")
    doc = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": "LC-" + frappe.generate_hash(length=20),
            "item_name": item_name.strip(),
            "item_group": item_group,
            "stock_uom": stock_uom,
            "lc_shop": shop_doc.name,
            "is_stock_item": 1,
            "item_defaults": [{"company": shop_doc.company}],
        }
    )
    token = _item_creation.set(True)
    try:
        # Only this allowlisted operation bypasses standard Item role permissions.
        # Normal ERPNext validations and transaction rollback remain enabled.
        doc.insert(ignore_permissions=True)
    finally:
        _item_creation.reset(token)
    return {key: doc.get(key) for key in ("name", "item_name", "item_group", "stock_uom")}
