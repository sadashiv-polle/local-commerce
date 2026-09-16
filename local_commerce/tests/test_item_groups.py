"""Run on a disposable ERPNext v15 site."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services.item_groups import COMMERCE_ITEM_GROUPS, ensure_item_groups


class TestCommerceItemGroups(FrappeTestCase):
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
