"""Category permissions, persistence, and search; run on a disposable v15 site."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services import category_menu, orders, products
from local_commerce.tests.test_owner_inventory import TestOwnerInventory


class TestCategoryMenu(FrappeTestCase):
    def setUp(self):
        TestOwnerInventory.setUp(self)

    def tearDown(self):
        TestOwnerInventory.tearDown(self)

    def test_owner_cannot_change_customer_menu(self):
        with self.assertRaises(frappe.PermissionError):
            category_menu.menu(admin=True)
        with self.assertRaises(frappe.PermissionError):
            category_menu.save_menu(0, [])
        with self.assertRaises(frappe.PermissionError):
            category_menu.upload_image()

    def test_hidden_menu_stays_hidden_after_migration_seeding(self):
        frappe.set_user("Administrator")
        category_menu.save_menu(0, [
            {"item_group": self.group, "label": "Test category",
             "section": "Test menu", "enabled": 1}
        ])
        category_menu.seed_menu()
        self.assertFalse(category_menu.menu()["enabled"])
        self.assertEqual(category_menu.menu()["categories"], [])
        self.assertEqual(category_menu.menu(admin=True)["categories"][0]["label"], "Test category")
        category_menu.save_menu(1, [
            {"item_group": self.group, "label": "Test category", "enabled": 0}
        ])
        self.assertEqual(category_menu.menu()["categories"], [])

    def test_category_opens_matching_products_without_search_text(self):
        other_group = frappe.get_all(
            "Item Group", filters={"is_group": 0, "name": ["!=", self.group]},
            pluck="name", limit_page_length=1,
        )[0]
        other_item = products.create_item(
            self.shop.name, "Other category product", other_group, self.uom
        )["name"]
        frappe.set_user("Administrator")
        self.shop.reload()
        self.shop.status = "Active"
        self.shop.save()
        frappe.set_user("Guest")
        result = orders.search_products("", category=self.group)
        names = {item["item"] for item in result["items"]}
        self.assertIn(self.item, names)
        self.assertNotIn(other_item, names)
        self.assertTrue(all(item["item_group"] == self.group for item in result["items"]))
