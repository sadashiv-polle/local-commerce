"""Delivery request integration tests; run on a disposable ERPNext v15 site."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services import customers, orders, owner
from local_commerce.tests.helpers import add_member, create_user
from local_commerce.tests.test_owner_inventory import TestOwnerInventory


class TestDeliveryOrders(FrappeTestCase):
    def setUp(self):
        TestOwnerInventory.setUp(self)
        owner.adjust_stock(
            self.shop.name, self.item, "Add", 5, "Test receipt", "order-stock-receipt", 10
        )
        item = frappe.get_doc("Item", self.item)
        owner.update_product(
            self.shop.name, self.item, str(item.modified), item.item_name, price=20
        )
        frappe.set_user("Administrator")
        self.customer = create_user("LC Customer")
        self.stranger = create_user("LC Customer")
        self.cash_account = frappe.db.get_value(
            "Account",
            {
                "company": self.shop.company,
                "account_type": "Cash",
                "is_group": 0,
                "disabled": 0,
            },
            "name",
        )
        self.cash_mode = frappe.db.get_value("Mode of Payment", {"name": "Cash"}, "name")
        self.assertTrue(self.cash_account, "Test Company requires a cash account")
        self.assertTrue(self.cash_mode, "ERPNext requires the Cash mode of payment")
        template = frappe.get_doc(
            {
                "doctype": "Sales Taxes and Charges Template",
                "title": "LC Test " + frappe.generate_hash(length=8),
                "company": self.shop.company,
                "taxes": [
                    {
                        "charge_type": "On Net Total",
                        "account_head": self.account,
                        "description": "Test zero tax",
                        "rate": 0,
                    }
                ],
            }
        ).insert()
        self.shop.reload()
        self.shop.update(
            {
                "status": "Active",
                "delivery_enabled": 1,
                "delivery_postcodes": "403001",
                "order_tax_template": template.name,
                "cod_enabled": 1,
                "cod_cash_account": self.cash_account,
                "cod_mode_of_payment": self.cash_mode,
            }
        )
        self.shop.save()
        settings = frappe.get_single("Selling Settings")
        if not settings.customer_group:
            settings.customer_group = frappe.get_all(
                "Customer Group", filters={"is_group": 0}, pluck="name", limit=1
            )[0]
        if not settings.territory:
            settings.territory = frappe.get_all("Territory", pluck="name", limit=1)[0]
        settings.save()
        self.address = dict(
            recipient="Customer",
            phone="1234567890",
            line1="Test street",
            city="Panaji",
            postal_code="403001",
        )
        frappe.set_user(self.customer.name)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def place(self, key="delivery-request-001", quantity=2):
        return orders.place(
            self.shop.name,
            [{"item": self.item, "quantity": quantity, "rate": 0}],
            self.address,
            key,
        )

    def test_request_replay_and_owner_acceptance(self):
        order = self.place()
        self.assertEqual(self.place()["name"], order["name"])
        doc = frappe.get_doc("LC Order", order["name"])
        so = frappe.get_doc("Sales Order", doc.sales_order)
        self.assertEqual(so.docstatus, 0)
        self.assertEqual(so.items[0].rate, 20)
        self.assertEqual(so.company, self.shop.company)
        frappe.set_user(self.user.name)
        orders.change(order["name"], "Accepted")
        so.reload()
        self.assertEqual(so.docstatus, 1)
        self.assertGreaterEqual(owner.balance(self.item, self.warehouse.name)["reserved"], 2)
        orders.change(order["name"], "Preparing")
        self.assertEqual(orders.change(order["name"], "Ready")["status"], "Ready")
        orders.change(order["name"], "Cancelled", "Customer requested cancellation")
        so.reload()
        self.assertEqual(so.docstatus, 2)

    def test_customer_and_cross_shop_isolation(self):
        order = self.place()
        frappe.set_user(self.stranger.name)
        self.assertEqual(orders.list_orders(), [])
        with self.assertRaises(frappe.PermissionError):
            orders.detail(order["name"])
        with self.assertRaises(frappe.PermissionError):
            orders.change(order["name"], "Accepted")
        frappe.set_user(self.customer.name)
        with self.assertRaises(frappe.ValidationError):
            orders.change(order["name"], "Accepted")
        self.assertEqual(
            orders.change(order["name"], "Cancelled", "No longer required")["status"], "Cancelled"
        )

    def test_replay_payload_and_postal_validation(self):
        self.place()
        with self.assertRaises(frappe.ValidationError):
            self.place(quantity=3)
        self.address["postal_code"] = "999999"
        with self.assertRaises(frappe.ValidationError):
            self.place(key="outside-delivery-zone")

    def test_shop_radius_requires_and_checks_customer_map_pin(self):
        frappe.set_user("Administrator")
        self.shop.reload()
        self.shop.update(
            {
                "address_line1": "Test market",
                "city": "Panaji",
                "postal_code": "403001",
                "latitude": 15.4909,
                "longitude": 73.8278,
                "service_radius_km": 2,
            }
        )
        self.shop.save()
        frappe.set_user(self.customer.name)
        self.address.update({"latitude": 15.4989, "longitude": 73.8278})
        placed = self.place(key="located-delivery-request")
        self.assertAlmostEqual(placed["delivery_distance_km"], 0.89, places=2)
        self.address.update({"latitude": 15.60, "longitude": 73.8278})
        with self.assertRaises(frappe.ValidationError):
            self.place(key="outside-map-radius")

    def test_saved_address_discovers_serviceable_shops_by_distance(self):
        frappe.set_user("Administrator")
        self.shop.reload()
        self.shop.update(
            {
                "address_line1": "Test market",
                "city": "Panaji",
                "postal_code": "403001",
                "latitude": 15.4909,
                "longitude": 73.8278,
                "service_radius_km": 2,
            }
        )
        self.shop.save()
        frappe.set_user(self.customer.name)
        saved = customers.save_address(
            None,
            "Home",
            "Home",
            "Customer",
            "1234567890",
            "Test street",
            "Panaji",
            "403001",
            15.4989,
            73.8278,
            True,
        )
        result = customers.nearby(saved["name"])
        located = next(row for row in result["shops"] if row.name == self.shop.name)
        self.assertTrue(located.serviceable)
        self.assertAlmostEqual(located.distance_km, 0.89, places=2)

    def test_acceptance_rechecks_stock(self):
        first = self.place(quantity=4)
        second = self.place(key="another-order-request", quantity=4)
        frappe.set_user(self.user.name)
        orders.change(first["name"], "Accepted")
        with self.assertRaises(frappe.ValidationError):
            orders.change(second["name"], "Accepted")

    def test_raw_status_edit_denied(self):
        order = self.place()
        doc = frappe.get_doc("LC Order", order["name"])
        doc.status = "Ready"
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)

    def test_guest_browses_without_delivery_but_checkout_stays_blocked(self):
        frappe.set_user("Administrator")
        self.shop.reload()
        self.shop.delivery_enabled = 0
        self.shop.save()
        frappe.set_user("Guest")
        catalog = orders.catalog(self.shop.name)
        self.assertFalse(catalog["accepting_orders"])
        self.assertIn(self.item, [row["item"] for row in catalog["items"]])
        frappe.set_user(self.customer.name)
        with self.assertRaises(frappe.ValidationError):
            self.place()

    def test_catalog_returns_item_image(self):
        frappe.set_user("Administrator")
        frappe.db.set_value("Item", self.item, "image", "/files/catalog-product.png")
        frappe.set_user("Guest")
        catalog = orders.catalog(self.shop.name)
        product = next(row for row in catalog["items"] if row["item"] == self.item)
        self.assertEqual(product["image"], "/files/catalog-product.png")

    def test_owner_assigns_driver_and_delivery_posts_stock(self):
        order = self.place()
        frappe.set_user("Administrator")
        driver = create_user("LC Delivery Person")
        add_member(self.shop, driver, "Driver")
        frappe.set_user(self.user.name)
        orders.change(order["name"], "Accepted")
        orders.change(order["name"], "Preparing")
        orders.change(order["name"], "Ready")
        assigned = orders.assign_driver(order["name"], driver.name)
        self.assertEqual(assigned["delivery_user"], driver.name)
        frappe.set_user(driver.name)
        profile = orders.delivery_profile()
        self.assertEqual(profile["metrics"]["active"], 1)
        self.assertEqual(profile["metrics"]["shops"], 1)
        self.assertEqual(len(orders.delivery_assignments()), 1)
        picked_up = orders.delivery_change(order["name"], "Picked Up")
        self.assertEqual(picked_up["status"], "Picked Up")
        self.assertEqual(frappe.session.user, driver.name)
        doc = frappe.get_doc("LC Order", order["name"])
        self.assertEqual(frappe.db.get_value("Delivery Note", doc.delivery_note, "docstatus"), 1)
        self.assertEqual(owner.balance(self.item, self.warehouse.name)["actual"], 3)
        out_for_delivery = orders.delivery_change(order["name"], "Out for Delivery")
        location = orders.update_driver_location(order["name"], 15.5, 73.8, 12)
        self.assertTrue(location["accepted"])
        self.assertEqual(orders.detail(order["name"])["driver_location"]["latitude"], 15.5)
        delivered = orders.delivery_change(
            order["name"], "Delivered", collected_amount=out_for_delivery["total"]
        )
        self.assertEqual(delivered["status"], "Delivered")
        self.assertTrue(delivered["delivered_at"])
        self.assertEqual(delivered["payment_status"], "Collected")
        self.assertFalse(delivered["payment_entry"])
        self.assertIsNone(frappe.db.get_value("LC Order", order["name"], "driver_latitude"))
        self.assertEqual(
            frappe.db.get_value("Sales Invoice", delivered["sales_invoice"], "docstatus"), 1
        )
        collection = frappe.db.get_value("LC COD Collection", {"order": order["name"]}, "name")
        self.assertTrue(collection)
        self.assertEqual(
            frappe.db.get_value("LC COD Collection", collection, "status"),
            "Awaiting Handover",
        )
        self.assertEqual(orders.delivery_assignments(), [])
        self.assertEqual(len(orders.delivery_assignments(view="history")), 1)
        profile = orders.delivery_profile()
        self.assertEqual(profile["metrics"]["delivered"], 1)
        self.assertEqual(profile["metrics"]["awaiting_handover"], 1)
        self.assertEqual(profile["cash_pending"][0]["amount"], delivered["total"])
        frappe.set_user(self.user.name)
        self.assertEqual(len(orders.cod_collections(self.shop.name)), 1)
        orders.reconcile_cod(collection)
        reconciled = orders.detail(order["name"])
        self.assertEqual(reconciled["payment_status"], "Reconciled")
        self.assertEqual(
            frappe.db.get_value("Payment Entry", reconciled["payment_entry"], "docstatus"), 1
        )
        self.assertEqual(
            frappe.db.get_value("Sales Invoice", reconciled["sales_invoice"], "outstanding_amount"),
            0,
        )
        self.assertEqual(orders.cod_collections(self.shop.name), [])
        self.assertEqual(len(orders.cod_collections(self.shop.name, view="history")), 1)

    def test_only_assigned_shop_driver_can_update_delivery(self):
        order = self.place()
        frappe.set_user("Administrator")
        driver = create_user("LC Delivery Person")
        other_driver = create_user("LC Delivery Person")
        add_member(self.shop, driver, "Driver")
        add_member(self.other, other_driver, "Driver")
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.ValidationError):
            orders.assign_driver(order["name"], other_driver.name)
        with self.assertRaises(frappe.ValidationError):
            orders.assign_driver(order["name"], driver.name)
        orders.change(order["name"], "Accepted")
        orders.change(order["name"], "Preparing")
        orders.change(order["name"], "Ready")
        orders.assign_driver(order["name"], driver.name)
        frappe.set_user(other_driver.name)
        with self.assertRaises(frappe.PermissionError):
            orders.delivery_change(order["name"], "Picked Up")
