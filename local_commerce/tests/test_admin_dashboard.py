"""Run on a disposable ERPNext v15 site; exercises admin data and mutations."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.permissions.policy import MEMBER_ROLES
from local_commerce.services import admin, products
from local_commerce.tests.helpers import create_user
from local_commerce.tests.test_owner_inventory import TestOwnerInventory


class TestAdminDashboard(FrappeTestCase):
    def setUp(self):
        TestOwnerInventory.setUp(self)

    def tearDown(self):
        TestOwnerInventory.tearDown(self)

    def test_every_admin_endpoint_rejects_owner_and_guest(self):
        for user in (self.user.name, "Guest"):
            frappe.set_user(user)
            operations = (
                lambda: admin.overview(),
                lambda: admin.listing("customers"),
                lambda: admin.setup_options(),
                lambda: admin.set_accepting(self.shop.name, 0),
                lambda: admin.create_shop("Unauthorized shop"),
                lambda: admin.save_membership(self.shop.name, self.user.name, "Delivery Person"),
            )
            for operation in operations:
                with self.assertRaises(frappe.PermissionError):
                    operation()

    def test_inventory_pages_are_bounded_and_use_live_stock(self):
        for index in range(24):
            products.create_item(self.shop.name, f"Admin page item {index}", self.group, self.uom)
        frappe.set_user("Administrator")
        first = admin.listing("inventory", shop=self.shop.name)
        second = admin.listing("inventory", shop=self.shop.name, start=20)
        self.assertEqual(len(first["items"]), 20)
        self.assertEqual(len(second["items"]), 5)
        self.assertTrue(first["has_more"])
        self.assertFalse(second["has_more"])
        self.assertFalse({row.name for row in first["items"]} &
                         {row.name for row in second["items"]})
        self.assertTrue(all(row.available == 0 for row in first["items"]))
        shops = admin.listing("shops", search=self.shop.shop_name)["items"]
        self.assertEqual([row.name for row in shops], [self.shop.name])
        with self.assertRaises(frappe.ValidationError):
            admin.listing("inventory", start=-1)
        with self.assertRaises(frappe.ValidationError):
            admin.listing("unknown-section")

    def test_order_pause_preserves_schedule_and_memberships_assign_roles(self):
        frappe.set_user("Administrator")
        before = self.shop.opening_hours_json
        admin.set_accepting(self.shop.name, 0)
        self.shop.reload()
        self.assertFalse(self.shop.accepting_orders)
        self.assertEqual(self.shop.opening_hours_json, before)
        driver = create_user("LC Customer")
        member = admin.save_membership(self.shop.name, driver.name, "Delivery Person")
        self.assertIn(MEMBER_ROLES["Delivery Person"], frappe.get_roles(driver.name))
        admin.save_membership(
            self.shop.name, driver.name, "Delivery Person", member["name"], enabled=0
        )
        self.assertFalse(frappe.db.get_value("LC Shop Member", member["name"], "enabled"))
        with self.assertRaises(frappe.ValidationError):
            admin.save_membership(self.other.name, driver.name, "Delivery Person", member["name"])

    def test_shop_creation_and_overview_return_actual_records(self):
        frappe.set_user("Administrator")
        name = "Admin shop " + frappe.generate_hash(length=8)
        result = admin.create_shop(name, country="United States", currency="USD")
        self.assertEqual(result["company"], name)
        self.assertEqual(frappe.db.get_value("LC Shop", result["name"], "status"), "Draft")
        overview = admin.overview()
        self.assertGreaterEqual(overview["shops"], 3)
        self.assertIn("cash_pending", overview)
        self.assertIn("sales_today", overview)
        self.assertIn("trend", overview)
