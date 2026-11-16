"""Add common selling units without changing existing inventory conventions."""
import frappe

# Portion sizes belong in product names; a Half Plate product still sells one Plate.
PRODUCT_UNITS = {
    'Kg': 0, 'Gram': 0, 'Litre': 0, 'Millilitre': 0,
    'Nos': 1, 'Pack': 1, 'Plate': 1, 'Bowl': 1, 'Cup': 1,
    'Glass': 1, 'Bottle': 1, 'Box': 1, 'Bunch': 1, 'Dozen': 1,
}


def ensure_product_units():
    for name, whole in PRODUCT_UNITS.items():
        if frappe.db.exists('UOM', name):
            # Preserve disabled units and whole-number rules on existing sites.
            continue
        frappe.get_doc(dict(doctype='UOM', uom_name=name, enabled=1,
                            must_be_whole_number=whole)).insert(ignore_permissions=True)
