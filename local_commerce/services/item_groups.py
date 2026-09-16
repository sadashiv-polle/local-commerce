"""Repeatable starter categories for commerce items and ERPNext stock records."""

import frappe

COMMERCE_ITEM_GROUPS = (
    "Fish",
    "Seafood",
    "Rice",
    "Groceries",
    "Fruits",
    "Vegetables",
    "Meat & Poultry",
    "Dairy & Eggs",
    "Bakery",
    "Fast Food",
    "Snacks",
    "Beverages",
    "Household Essentials",
    "Personal Care",
)


def ensure_item_groups():
    # Find the actual tree root rather than assuming its name on restored sites.
    root = frappe.db.get_value("Item Group", {"lft": 1, "is_group": 1}, "name")
    if not root:
        frappe.throw("Set up the ERPNext Item Group tree before installing Local Commerce")
    for name in COMMERCE_ITEM_GROUPS:
        # Existing groups may already have items or a different parent. Preserve them.
        if frappe.db.exists("Item Group", name):
            continue
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": name,
                "parent_item_group": root,
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
