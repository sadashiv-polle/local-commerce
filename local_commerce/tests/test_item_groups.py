"""Run on a disposable ERPNext v15 site."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services.item_groups import COMMERCE_ITEM_GROUPS, ensure_item_groups


class TestCommerceItemGroups(FrappeTestCase):
    def test_setup_completion_restores_missing_categories_without_rewriting_existing(self):
        from local_commerce.install import after_setup

        frappe.set_user("Administrator")
        ensure_item_groups()
        rice = frappe.db.get_value("Item Group", "Rice", "modified")
        # Simulate a fresh setup ending with only ERPNext's standard groups.
        frappe.db.delete("Item Group", {"name": "Fish"})
        after_setup({"country": "India"})
        self.assertTrue(frappe.db.exists("Item Group", "Fish"))
        self.assertEqual(frappe.db.get_value("Item Group", "Rice", "modified"), rice)
        self.assertEqual(frappe.db.get_value("Item Group", "Fish", "is_group"), 0)

    def test_starter_categories_are_repeatable_and_preserve_existing_groups(self):
        frappe.set_user("Administrator")
        ensure_item_groups()
        original = {
            name: frappe.db.get_value(
                "Item Group", name, ["parent_item_group", "is_group", "modified"]
            )
            for name in COMMERCE_ITEM_GROUPS
        }
        ensure_item_groups()
        for name, values in original.items():
            self.assertIsNotNone(values)
            self.assertEqual(
                frappe.db.get_value(
                    "Item Group", name, ["parent_item_group", "is_group", "modified"]
                ),
                values,
            )
