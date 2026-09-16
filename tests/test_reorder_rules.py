import unittest

from local_commerce.services.reorder_rules import reorder_line


class ReorderTests(unittest.TestCase):
    def setUp(self):
        self.previous = {"name": "Fish", "quantity": 3, "uom": "Kg", "rate": 100}
        self.product = {"item": "fish", "uom": "Kg", "rate": 100, "available": 5}

    def test_available_item_keeps_quantity(self):
        line, notice = reorder_line(self.previous, self.product)
        self.assertEqual(line["quantity"], 3)
        self.assertIsNone(notice)

    def test_current_stock_and_price_replace_old_values(self):
        line, notice = reorder_line(self.previous, {**self.product, "available": 2, "rate": 120})
        self.assertEqual(line["quantity"], 2)
        self.assertEqual(line["rate"], 120)
        self.assertIn("quantity reduced", notice)
        self.assertIn("price updated", notice)

    def test_unavailable_items_are_explained(self):
        for product in (None, {**self.product, "available": 0}, {**self.product, "rate": None}):
            line, notice = reorder_line(self.previous, product)
            self.assertIsNone(line)
            self.assertTrue(notice)

    def test_changed_units_are_not_silently_reordered(self):
        line, notice = reorder_line(self.previous, {**self.product, "uom": "Nos"})
        self.assertIsNone(line)
        self.assertIn("selling unit changed", notice)
