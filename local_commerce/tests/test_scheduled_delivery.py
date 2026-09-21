"""Run on a disposable ERPNext v15 site, never on production test orders."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from local_commerce.services import orders, scheduled
from local_commerce.tests.test_orders import TestDeliveryOrders


class TestScheduledDelivery(FrappeTestCase):
    def setUp(self):
        TestDeliveryOrders.setUp(self)
        frappe.set_user("Administrator")
        self.shop.reload()
        self.shop.delivery_fee = 35
        self.shop.scheduled_enabled = 1
        self.shop.save()
        now = now_datetime()
        self.slot = frappe.get_doc(
            {
                "doctype": "LC Delivery Slot",
                "shop": self.shop.name,
                "title": "Evening batch",
                "enabled": 1,
                "ordering_start": add_to_date(now, hours=-1),
                "ordering_end": add_to_date(now, hours=1),
                "delivery_start": add_to_date(now, hours=2),
                "delivery_end": add_to_date(now, hours=3),
                "capacity": 2,
                "radius_km": 5,
                "products": self.item,
                "postcodes": "403001",
            }
        ).insert()
        frappe.set_user(self.customer.name)

    def tearDown(self):
        TestDeliveryOrders.tearDown(self)

    def request(self, key="scheduled-test-order-001"):
        return orders.place(
            self.shop.name,
            [{"item": self.item, "quantity": 1}],
            self.address,
            key,
            delivery_mode="Scheduled",
            scheduled_slot=self.slot.name,
        )

    def test_scheduled_free_normal_charged_and_retry_keeps_original(self):
        first = self.request()
        self.assertEqual(first["total"], 20)
        self.assertEqual(self.request()["name"], first["name"])
        normal = orders.place(
            self.shop.name,
            [{"item": self.item, "quantity": 1}],
            self.address,
            "normal-comparison-test-001",
        )
        self.assertEqual(normal["total"], 55)
        self.request("scheduled-test-order-002")
        with self.assertRaises(frappe.ValidationError):
            self.request("scheduled-test-order-003")
        with self.assertRaises(frappe.ValidationError):
            orders.place(
                self.shop.name,
                [{"item": self.item, "quantity": 1}],
                self.address,
                "scheduled-test-order-001",
            )

    def test_customer_cannot_configure_or_read_batch(self):
        with self.assertRaises(frappe.PermissionError):
            scheduled.configure(self.shop.name, 0, 1)
        self.request()
        with self.assertRaises(frappe.PermissionError):
            scheduled.batch(self.slot.name)

    def test_scheduled_only_ignores_normal_opening_hours(self):
        frappe.set_user("Administrator")
        self.shop.reload()
        self.shop.delivery_enabled = 0
        self.shop.accepting_orders = 0
        self.shop.save()
        frappe.set_user(self.customer.name)
        request = self.request()
        self.assertEqual(request["delivery_mode"], "Scheduled")
        frappe.set_user(self.user.name)
        accepted = orders.change(request["name"], "Accepted")
        self.assertEqual(accepted["status"], "Accepted")
        self.assertEqual(accepted["total"], 20)
        frappe.set_user(self.customer.name)
        with self.assertRaises(frappe.ValidationError):
            orders.place(
                self.shop.name,
                [{"item": self.item, "quantity": 1}],
                self.address,
                "disabled-normal-test-001",
            )

    def test_owner_accepts_individually_then_advances_closed_batch(self):
        first = self.request()
        second = self.request("scheduled-test-second-order")
        frappe.set_user("Administrator")
        frappe.db.set_value(
            "LC Delivery Slot",
            self.slot.name,
            "ordering_end",
            add_to_date(now_datetime(), minutes=-1),
        )
        frappe.set_user(self.user.name)
        orders.change(first["name"], "Accepted")
        with self.assertRaises(frappe.ValidationError):
            scheduled.advance_batch(self.slot.name, "Preparing")
        orders.change(second["name"], "Accepted")
        self.assertEqual(scheduled.advance_batch(self.slot.name, "Preparing")["changed"], 2)
        self.assertEqual(scheduled.advance_batch(self.slot.name, "Preparing")["changed"], 0)
        self.assertEqual(scheduled.advance_batch(self.slot.name, "Ready")["changed"], 2)
        for name in (first["name"], second["name"]):
            self.assertEqual(frappe.db.get_value("LC Order", name, "status"), "Ready")
        with self.assertRaises(frappe.ValidationError):
            scheduled.advance_batch(self.slot.name, "Delivered")
