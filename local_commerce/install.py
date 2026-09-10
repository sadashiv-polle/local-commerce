"""Install checks and repeatable schema constraints. Never edit ERPNext core."""

import frappe


def before_install():
    import erpnext

    if frappe.__version__.split(".")[0] != "15" or erpnext.__version__.split(".")[0] != "15":
        frappe.throw("Local Commerce requires Frappe 15 and ERPNext 15")
    before_migrate()
    for name in (
        "LC Shop",
        "LC Shop Member",
        "LC Stock Operation",
        "LC Order",
        "LC Customer Account",
    ):
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
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    existing = frappe.get_meta("Item").get_field("lc_shop")
    if existing and (existing.fieldtype != "Link" or existing.options != "LC Shop"):
        frappe.throw("Item.lc_shop field collision: expected a Link to LC Shop")
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "lc_shop",
                    "label": "Local Commerce Shop",
                    "fieldtype": "Link",
                    "options": "LC Shop",
                    "read_only": 1,
                    "no_copy": 1,
                    "search_index": 1,
                    "insert_after": "item_name",
                }
            ]
        }
    )

    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "lc_creation_key",
                    "label": "LC Creation Key",
                    "fieldtype": "Data",
                    "unique": 1,
                    "read_only": 1,
                    "hidden": 1,
                    "no_copy": 1,
                },
                {
                    "fieldname": "lc_sold_out",
                    "label": "Local Commerce Sold Out",
                    "fieldtype": "Check",
                    "default": "0",
                    "read_only": 1,
                },
                {
                    "fieldname": "lc_low_stock",
                    "label": "Local Commerce Low Stock Threshold",
                    "fieldtype": "Float",
                    "default": "0",
                    "read_only": 1,
                },
                {
                    "fieldname": "lc_description",
                    "label": "Local Commerce Description",
                    "fieldtype": "Small Text",
                    "read_only": 1,
                },
            ],
            "Stock Entry": [
                {
                    "fieldname": "lc_shop",
                    "label": "Local Commerce Shop",
                    "fieldtype": "Link",
                    "options": "LC Shop",
                    "read_only": 1,
                    "no_copy": 1,
                    "search_index": 1,
                }
            ],
        }
    )
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "lc_order",
                    "label": "Local Commerce Order",
                    "fieldtype": "Link",
                    "options": "LC Order",
                    "read_only": 1,
                    "no_copy": 1,
                    "unique": 1,
                }
            ],
            "Delivery Note": [
                {
                    "fieldname": "lc_order",
                    "label": "Local Commerce Order",
                    "fieldtype": "Link",
                    "options": "LC Order",
                    "read_only": 1,
                    "no_copy": 1,
                    "unique": 1,
                }
            ],
            "Sales Invoice": [
                {
                    "fieldname": "lc_order",
                    "label": "Local Commerce Order",
                    "fieldtype": "Link",
                    "options": "LC Order",
                    "read_only": 1,
                    "no_copy": 1,
                    "unique": 1,
                }
            ],
            "Payment Entry": [
                {
                    "fieldname": "lc_order",
                    "label": "Local Commerce Order",
                    "fieldtype": "Link",
                    "options": "LC Order",
                    "read_only": 1,
                    "no_copy": 1,
                    "unique": 1,
                }
            ],
            "Customer": [
                {
                    "fieldname": "lc_customer_key",
                    "label": "LC Customer Key",
                    "fieldtype": "Data",
                    "read_only": 1,
                    "hidden": 1,
                    "unique": 1,
                    "no_copy": 1,
                }
            ],
        }
    )
    if frappe.db.has_column("LC Order", "payment_method"):
        frappe.db.sql(
            """update `tabLC Order`
            set payment_method='Cash on Delivery', payment_status='Pending'
            where status in ('Requested', 'Accepted', 'Preparing', 'Ready',
                'Picked Up', 'Out for Delivery')
            and coalesce(payment_method, '')=''"""
        )
    frappe.db.add_unique("LC Shop Member", ["shop", "user"], "lc_shop_member_unique")


def before_migrate():
    for name in (
        "LC Shop",
        "LC Shop Member",
        "LC Stock Operation",
        "LC Order",
        "LC Customer Account",
    ):
        module = frappe.db.get_value("DocType", name, "module")
        if module and module != "Local Commerce":
            frappe.throw(f"DocType collision: {name} belongs to {module}")
    for doctype, field, fieldtype, options in (
        ("Sales Order", "lc_order", "Link", "LC Order"),
        ("Delivery Note", "lc_order", "Link", "LC Order"),
        ("Sales Invoice", "lc_order", "Link", "LC Order"),
        ("Payment Entry", "lc_order", "Link", "LC Order"),
        ("Customer", "lc_customer_key", "Data", None),
        ("Item", "lc_shop", "Link", "LC Shop"),
        ("Item", "lc_creation_key", "Data", None),
        ("Item", "lc_description", "Small Text", None),
        ("Item", "lc_low_stock", "Float", None),
        ("Item", "lc_sold_out", "Check", None),
        ("Stock Entry", "lc_shop", "Link", "LC Shop"),
    ):
        existing = frappe.get_meta(doctype).get_field(field)
        if existing and (
            existing.fieldtype != fieldtype or (options and existing.options != options)
        ):
            frappe.throw(f"Custom field collision: {doctype}.{field}")
