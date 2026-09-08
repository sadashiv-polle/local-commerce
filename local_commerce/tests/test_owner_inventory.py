"""Run on a disposable ERPNext v15 site: exercises actual stock and price records."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services import owner, products
from local_commerce.tests.helpers import add_member, create_shop, create_user


class TestOwnerInventory(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.shop = create_shop()
        self.other = create_shop()
        self.user = create_user("LC Shop Owner")
        self.member = add_member(self.shop, self.user)
        self.warehouse = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": "LC " + frappe.generate_hash(length=8),
                "company": self.shop.company,
                "is_group": 0,
            }
        ).insert()
        self.account = frappe.db.get_value(
            "Account",
            {
                "company": self.shop.company,
                "account_type": "Stock Adjustment",
                "is_group": 0,
                "disabled": 0,
            },
            "name",
        )
        self.center = frappe.db.get_value(
            "Cost Center", {"company": self.shop.company, "is_group": 0, "disabled": 0}, "name"
        )
        self.assertTrue(self.account, "Test Company requires a Stock Adjustment account")
        self.assertTrue(self.center, "Test Company requires a leaf cost center")
        owner.configure(self.shop.name, self.warehouse.name, self.account, self.center)
        self.group = frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0]
        self.uom = frappe.get_all("UOM", filters={"enabled": 1}, pluck="name")[0]
        frappe.set_user(self.user.name)
        self.item = products.create_item(self.shop.name, "Inventory test", self.group, self.uom)[
            "name"
        ]

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def move(self, action="Add", qty=5, key="receipt-request-00001", cost=10):
        return owner.adjust_stock(
            self.shop.name, self.item, action, qty, "Test stock count", key, cost
        )

    def test_receipt_issue_and_replay_create_real_submitted_entries(self):
        result = self.move()
        duplicate = self.move()
        self.assertEqual(result["stock_entry"], duplicate["stock_entry"])
        self.assertTrue(duplicate["replayed"])
        entry = frappe.get_doc("Stock Entry", result["stock_entry"])
        self.assertEqual(entry.docstatus, 1)
        self.assertEqual(entry.company, self.shop.company)
        self.assertEqual(entry.items[0].t_warehouse, self.warehouse.name)
        ledger = frappe.get_all(
            "Stock Ledger Entry",
            filters={"voucher_no": entry.name, "is_cancelled": 0},
            fields=["company", "warehouse", "actual_qty"],
        )
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0].company, self.shop.company)
        self.assertEqual(ledger[0].warehouse, self.warehouse.name)
        self.assertEqual(ledger[0].actual_qty, 5)
        if frappe.db.get_value("Company", self.shop.company, "enable_perpetual_inventory"):
            entries = frappe.get_all(
                "GL Entry",
                filters={"voucher_no": entry.name, "is_cancelled": 0},
                fields=["company", "debit", "credit"],
            )
            self.assertTrue(entries)
            self.assertTrue(all(e.company == self.shop.company for e in entries))
            self.assertAlmostEqual(sum(e.debit - e.credit for e in entries), 0)

        self.assertEqual(owner.balance(self.item, self.warehouse.name)["actual"], 5)
        self.move("Remove", 2, "issue-request-000001", 0)
        self.assertEqual(owner.balance(self.item, self.warehouse.name)["actual"], 3)
        self.assertEqual(len(owner.history(self.shop.name, self.item)), 2)

    def test_reused_key_with_changed_payload_is_rejected(self):
        self.move()
        with self.assertRaises(frappe.ValidationError):
            self.move(qty=6)
        self.assertEqual(owner.balance(self.item, self.warehouse.name)["actual"], 5)

    def test_insufficient_stock_does_not_create_an_operation(self):
        with self.assertRaises(frappe.ValidationError):
            self.move("Remove", 1)
        self.assertEqual(owner.history(self.shop.name, self.item), [])

    def test_cross_shop_stock_and_configuration_denied(self):
        with self.assertRaises(frappe.PermissionError):
            owner.adjust_stock(
                self.other.name, self.item, "Add", 1, "Received", "cross-shop-request-1", 10
            )
        with self.assertRaises(frappe.PermissionError):
            owner.configure(self.other.name, self.warehouse.name, self.account, self.center)
        with self.assertRaises(frappe.PermissionError):
            owner.history(self.other.name, self.item)

    def test_foreign_warehouse_is_rejected(self):
        frappe.set_user("Administrator")
        foreign = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": "LC " + frappe.generate_hash(length=8),
                "company": self.other.company,
                "is_group": 0,
            }
        ).insert()
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.ValidationError):
            owner.configure(self.shop.name, foreign.name, self.account, self.center)

    def test_staff_can_read_but_cannot_adjust(self):
        frappe.set_user("Administrator")
        staff = create_user("LC Shop Staff")
        add_member(self.shop, staff, "Staff")
        frappe.set_user(staff.name)
        self.assertEqual(owner.catalog(self.shop.name)["total"], 1)
        with self.assertRaises(frappe.PermissionError):
            self.move()

    def test_revoked_owner_cannot_replay_or_read(self):
        self.move()
        frappe.set_user("Administrator")
        self.member.enabled = 0
        self.member.save()
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.PermissionError):
            self.move()
        with self.assertRaises(frappe.PermissionError):
            owner.catalog(self.shop.name)

    def test_sold_out_and_archive_preserve_stock(self):
        self.move()
        item = owner.detail(self.shop.name, self.item)
        updated = owner.update_product(
            self.shop.name,
            self.item,
            str(item["modified"]),
            "Updated",
            sold_out=1,
            low_stock=2,
            price=25,
        )
        self.assertEqual(updated["availability"], "Manually sold out")
        self.assertEqual(updated["stock"]["actual"], 5)
        self.assertEqual(updated["price"], 25)
        archived = owner.update_product(
            self.shop.name, self.item, str(updated["modified"]), "Updated", archived=1
        )
        self.assertEqual(archived["availability"], "Archived")
        self.assertEqual(archived["stock"]["actual"], 5)

    def test_stale_product_edit_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            owner.update_product(self.shop.name, self.item, "2000-01-01", "Stale")

    def test_creation_retry_returns_same_item(self):
        first = products.create_item(
            self.shop.name, "Retry test", self.group, self.uom, "create-request-00001"
        )
        second = products.create_item(
            self.shop.name, "Retry test", self.group, self.uom, "create-request-00001"
        )
        self.assertEqual(first["name"], second["name"])

    def test_raw_financial_resource_access_denied_with_broad_role(self):
        frappe.set_user("Administrator")
        self.user.add_roles("Stock Manager")
        frappe.set_user(self.user.name)
        result = self.move()
        entry = frappe.get_doc("Stock Entry", result["stock_entry"])
        with self.assertRaises(frappe.PermissionError):
            entry.check_permission("read")
        self.assertEqual(frappe.get_list("Stock Entry"), [])
