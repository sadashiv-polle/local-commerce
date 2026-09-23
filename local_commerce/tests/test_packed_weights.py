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
        self.assertFalse(request["estimated"])
        self.assertAlmostEqual(sum(row["amount"] for row in request["items"]), 495)
        frappe.set_user(self.user.name)
        accepted = orders.change(request["name"], "Accepted")
        preparing = orders.change(request["name"], "Preparing")
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

    def test_piece_pricing_keeps_bill_fixed_and_stock_uses_packed_weight(self):
        frappe.set_user(self.user.name)
        self.offers[0].update(billing="Pieces", piece_price=35)
        item = frappe.get_doc("Item", self.item)
        owner.update_product(self.shop.name, self.item, str(item.modified), item.item_name,
                             selling_options=self.offers)
        frappe.set_user(self.customer.name)
        request = self.request()
        self.assertAlmostEqual(sum(row["amount"] for row in request["items"]), 545)
        frappe.set_user(self.user.name)
        accepted = orders.change(request["name"], "Accepted")
        final = packing.finalize(request["name"], accepted["modified"], {"0": 1.02, "1": 0.47})
        self.assertAlmostEqual(sum(row["amount"] for row in final["items"]), 551)
        so = frappe.get_doc("Sales Order", frappe.db.get_value(
            "LC Order", request["name"], "sales_order"))
        self.assertEqual(so.items[1].uom, "Nos")
        self.assertEqual(so.items[1].qty, 7)
        self.assertAlmostEqual(so.items[1].stock_qty, 0.47)
        self.assertAlmostEqual(so.items[1].amount, 245)
        updated = packing.finalize(request["name"], final["modified"], {"0": 1.02, "1": 0.54})
        self.assertAlmostEqual(sum(row["amount"] for row in updated["items"]), 551)

    def test_hidden_options_are_not_public_or_orderable(self):
        frappe.set_user(self.user.name)
        self.offers[1]["enabled"] = False
        item = frappe.get_doc("Item", self.item)
        owner.update_product(self.shop.name, self.item, str(item.modified), item.item_name,
                             selling_options=self.offers)
        frappe.set_user(self.customer.name)
        public = orders.product_data(self.shop, frappe.get_doc("Item", self.item), browsing=True)
        self.assertEqual([row["id"] for row in public["selling_options"]], ["seven"])
        with self.assertRaises(frappe.ValidationError):
            self.request()

    def test_three_pieces_at_150_with_half_kg_estimate(self):
        frappe.set_user(self.user.name)
        item = frappe.get_doc("Item", self.item)
        offers = [{"id": "three", "label": "Three pieces", "kind": "Count",
                   "quantity": 3, "estimated_weight": 0.5,
                   "billing": "Pieces", "piece_price": 150}]
        owner.update_product(self.shop.name, self.item, str(item.modified), item.item_name,
                             selling_options=offers)
        frappe.set_user(self.customer.name)
        request = orders.place(self.shop.name,
                               [{"item": self.item, "option_id": "three", "quantity": 1}],
                               self.address, "three-piece-rounding-test")
        self.assertAlmostEqual(sum(row["amount"] for row in request["items"]), 450)
        frappe.set_user(self.user.name)
        accepted = orders.change(request["name"], "Accepted")
        final = packing.finalize(request["name"], accepted["modified"], {"0": 0.55})
        self.assertAlmostEqual(sum(row["amount"] for row in final["items"]), 450)
        so = frappe.get_doc("Sales Order", frappe.db.get_value(
            "LC Order", request["name"], "sales_order"))
        self.assertEqual(so.items[0].qty, 3)
        self.assertEqual(so.items[0].rate, 150)
        self.assertAlmostEqual(so.items[0].stock_qty, 0.55, delta=0.002)

    def test_preweighed_fish_snapshot_is_final_at_checkout(self):
        product = {"item": self.item, "uom": "Kg", "rate": 800,
                   "preweighed_weights": True, "selling_options": [
                       {"id": "530g", "label": "530 g", "kind": "Weight", "quantity": 0.53}]}
        quantity, snapshot = orders.selling_quantity(
            product, {"option_id": "530g", "quantity": 2})
        self.assertEqual(float(quantity), 1.06)
        self.assertEqual(snapshot["actual_weight"], 1.06)
        self.assertTrue(snapshot["preweighed"])
        self.assertEqual(float(quantity) * snapshot["rate_per_kg"], 848)
        product["preweighed_weights"] = False
        _, legacy = orders.selling_quantity(product, {"option_id": "530g", "quantity": 1})
        self.assertIsNone(legacy["actual_weight"])

    def test_ready_without_weight_confirmation_keeps_order_price_and_quantity(self):
        request = self.request()
        frappe.set_user(self.user.name)
        orders.change(request["name"], "Accepted")
        before = orders.change(request["name"], "Preparing")
        ready = orders.change(request["name"], "Ready")
        self.assertEqual(ready["status"], "Ready")
        self.assertEqual(ready["total"], before["total"])
        self.assertEqual(ready["items"], before["items"])
