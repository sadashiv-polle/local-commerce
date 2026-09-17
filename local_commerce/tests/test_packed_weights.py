"""Run on a disposable ERPNext v15 site with Local Commerce installed."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services import orders, owner, packing, products
from local_commerce.tests.test_orders import TestDeliveryOrders


class TestPackedWeights(FrappeTestCase):
    def setUp(self):
        TestDeliveryOrders.setUp(self)
        frappe.set_user(self.user.name)
        self.fish = products.create_item(self.shop.name, "Packing test fish", self.group, "Kg")
        self.item = self.fish["name"]
        owner.adjust_stock(self.shop.name, self.item, "Add", 10, "Fish receipt",
                           "packing-stock-receipt", 100)
        self.offers = [{"id": "seven", "label": "Seven fish", "kind": "Count",
                        "quantity": 7, "estimated_weight": 0.65},
                       {"id": "kg", "label": "One kilogram", "kind": "Weight", "quantity": 1}]
        item = frappe.get_doc("Item", self.item)
        owner.update_product(self.shop.name, self.item, str(item.modified), item.item_name,
                             price=300, selling_options=self.offers)
        frappe.set_user(self.customer.name)

    def tearDown(self):
        TestDeliveryOrders.tearDown(self)

    def request(self):
        return orders.place(self.shop.name,
                            [{"item": self.item, "option_id": "seven", "quantity": 1},
                             {"item": self.item, "option_id": "kg", "quantity": 1}],
                            self.address, "packing-order-request-001")

    def test_actual_weights_amend_sales_order_and_gate_ready(self):
        request = self.request()
        self.assertTrue(request["estimated"])
        self.assertAlmostEqual(sum(row["amount"] for row in request["items"]), 495)
        frappe.set_user(self.user.name)
        accepted = orders.change(request["name"], "Accepted")
        preparing = orders.change(request["name"], "Preparing")
        with self.assertRaises(frappe.ValidationError):
            orders.change(request["name"], "Ready")
        old_so = frappe.db.get_value("LC Order", request["name"], "sales_order")
        result = packing.finalize(request["name"], preparing["modified"], {"0": 1.02, "1": 0.47})
        self.assertFalse(result["estimated"])
        self.assertAlmostEqual(sum(row["amount"] for row in result["items"]), 447)
        new_so = frappe.db.get_value("LC Order", request["name"], "sales_order")
        self.assertNotEqual(old_so, new_so)
        self.assertEqual(frappe.db.get_value("Sales Order", old_so, "docstatus"), 2)
        self.assertEqual(frappe.db.get_value("Sales Order", new_so, "docstatus"), 1)
        self.assertEqual(frappe.db.get_value("Sales Order", new_so, "amended_from"), old_so)
        self.assertEqual(orders.change(request["name"], "Ready")["status"], "Ready")
        with self.assertRaises(frappe.ValidationError):
            packing.finalize(request["name"], result["modified"], {"0": 1, "1": 1})
        self.assertNotEqual(accepted["status"], "Ready")

    def test_packing_denies_customer_and_rolls_back_oversized_weight(self):
        request = self.request()
        with self.assertRaises(frappe.PermissionError):
            packing.finalize(request["name"], request["modified"], {"0": 1, "1": 1})
        frappe.set_user(self.user.name)
        accepted = orders.change(request["name"], "Accepted")
        original = frappe.db.get_value("LC Order", request["name"], "sales_order")
        with self.assertRaises(frappe.ValidationError):
            packing.finalize(request["name"], accepted["modified"], {"0": 20, "1": 1})
        self.assertEqual(frappe.db.get_value("LC Order", request["name"], "sales_order"), original)
        self.assertEqual(frappe.db.get_value("Sales Order", original, "docstatus"), 1)

    def test_invalid_option_and_combined_overbooking_are_rejected(self):
        for rows in [[{"item": self.item, "quantity": 1}],
                     [{"item": self.item, "option_id": "removed", "quantity": 1}],
                     [{"item": self.item, "option_id": "seven", "quantity": 10},
                      {"item": self.item, "option_id": "kg", "quantity": 5}]]:
            with self.assertRaises(frappe.ValidationError):
                orders.place(self.shop.name, rows, self.address, "invalid-packing-request-001")
