import unittest
from decimal import Decimal

from local_commerce.services.owner_rules import availability, number, stock_change


class OwnerRulesTests(unittest.TestCase):
    def test_weighted_receipt_keeps_decimal_quantity_and_cost(self):
        qty, cost = stock_change("Add", "1.250", "150.25", 0, 0)
        self.assertEqual(qty, Decimal("1.25"))
        self.assertEqual(cost, Decimal("150.25"))

    def test_negative_nonfinite_and_excess_precision_rejected(self):
        for value in ("-1", "NaN", "Infinity", "-Infinity", "x", "0.0000001", "1e100"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                number(value, "Rate")

    def test_receipt_requires_positive_cost_and_quantity(self):
        for qty, rate in [("0", "5"), ("1", "0"), ("-1", "5")]:
            with self.assertRaises(ValueError):
                stock_change("Add", qty, rate, 0, 0)

    def test_cannot_remove_committed_stock(self):
        with self.assertRaisesRegex(ValueError, "unreserved"):
            stock_change("Remove", 3, 0, 5, 3)
        self.assertEqual(stock_change("Remove", 2, 0, 5, 3)[0], Decimal(2))

    def test_whole_uom_rejects_fraction(self):
        with self.assertRaises(ValueError):
            stock_change("Add", "1.25", "5", 0, 0, True)

    def test_remove_never_uses_client_valuation(self):
        self.assertEqual(stock_change("Remove", 1, "invalid", 5, 0)[1], 0)

    def test_unknown_operation_rejected(self):
        with self.assertRaises(ValueError):
            stock_change("Sell", 1, 2, 5, 0)

    def test_availability_separates_pausing_archiving_and_stock(self):
        self.assertEqual(availability(5), "In stock")
        self.assertEqual(availability(0), "Out of stock")
        self.assertEqual(availability(5, True), "Manually sold out")
        self.assertEqual(availability(5, True, True), "Archived")
