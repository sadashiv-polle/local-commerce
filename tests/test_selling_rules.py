import unittest

from local_commerce.services.order_rules import cart_rows
from local_commerce.services.selling_rules import (
    options,
    packed_weights,
    selected,
    stock_weight_matches,
)


class TestSellingRules(unittest.TestCase):
    def offers(self):
        return [{"id": "custom", "label": "7 fish", "kind": "Count", "quantity": 7,
                 "estimated_weight": 0.65},
                {"id": "weight", "label": "Family pack", "kind": "Weight", "quantity": 1.25}]

    def test_custom_counts_and_fractional_weights(self):
        self.assertEqual(options(self.offers())[1]["estimated_weight"], 1.25)
        self.assertEqual(selected(self.offers(), "custom", 2)["estimated_total_weight"], 1.3)
        with self.assertRaises(ValueError):
            selected(self.offers(), "deleted", 1)
        with self.assertRaises(ValueError):
            selected(self.offers(), "custom", 0.5)

    def test_invalid_configuration(self):
        for rows in [self.offers() + self.offers(),
                     [{**self.offers()[0], "quantity": 1.5}],
                     [{**self.offers()[0], "estimated_weight": 0}],
                     [{**self.offers()[0], "label": ""}],
                     [{**self.offers()[0], "id": "bad::id"}]]:
            with self.assertRaises(ValueError):
                options(rows)

    def test_fractional_piece_error_identifies_option_and_weight_field(self):
        with self.assertRaisesRegex(ValueError, '7 fish.*whole number of pieces.*Approx. weight'):
            options([{**self.offers()[0], "quantity": 0.5}])
        self.assertEqual(options([{**self.offers()[1], "quantity": 0.5}])[0]["quantity"], 0.5)

    def test_piece_prices_and_visibility(self):
        rows = [{**self.offers()[0], "billing": "Pieces", "piece_price": 35},
                {**self.offers()[1], "enabled": False}]
        offer = selected(rows, "custom", 3)
        self.assertEqual(offer["piece_price"] * offer["quantity"] * offer["packs"], 735)
        self.assertEqual(offer["estimated_total_weight"], 1.95)
        with self.assertRaises(ValueError):
            selected(rows, "weight", 1)
        for invalid in [{**rows[0], "piece_price": 0},
                        {**rows[0], "piece_price": None},
                        {**rows[0], "enabled": "false"},
                        {**rows[1], "billing": "Pieces", "piece_price": 35}]:
            with self.assertRaises(ValueError):
                options([invalid])
        with self.assertRaises(ValueError):
            options([{**rows[0], "enabled": False}])
        # Earlier count offers retain actual-weight pricing until explicitly changed.
        self.assertEqual(selected(self.offers(), "custom", 1)["billing"], "Weight")

    def test_same_item_can_have_separate_options_without_trusting_client_price(self):
        result = cart_rows([{"item": "fish", "option_id": "custom", "quantity": 2,
                             "rate": 0, "estimated_weight": 0},
                            {"item": "fish", "option_id": "weight", "quantity": 1}])
        self.assertEqual(len(result), 2)
        self.assertNotIn("rate", result[0])
        self.assertNotIn("estimated_weight", result[0])
        with self.assertRaises(ValueError):
            cart_rows([result[0], result[0]])

    def test_packing_requires_every_weighted_line_and_no_extra_lines(self):
        lines = [{"option_id": "custom"}, {}, {"option_id": "weight"}]
        self.assertEqual(packed_weights(lines, {"0": "0.47", "2": "1.02"}),
                         {0: 0.47, 2: 1.02})
        for entries in [{"0": 0.47}, {"0": 0.47, "1": 1, "2": 1},
                        {"0": 0, "2": 1}, {"0": "NaN", "2": 1}]:
            with self.assertRaises(ValueError):
                packed_weights(lines, entries)


class TestPieceStockPrecision(unittest.TestCase):
    def test_three_piece_half_kg_pack_and_multipacks(self):
        for actual, expected, pieces in [(0.500001, 0.5, 3), (0.499999999999, 0.5, 3),
                                         (1.000002, 1, 6), (0.550002, 0.55, 3)]:
            self.assertTrue(stock_weight_matches(actual, expected, pieces, 6, 6))

    def test_real_weight_changes_and_coarse_rounding_remain_rejected(self):
        for actual, expected, pieces, precision in [(0.51, 0.5, 3, 6), (0.51, 0.5, 3, 3),
                                                    (0, 0.5, 3, 6), (0.6, 0.5, 300, 2)]:
            self.assertFalse(stock_weight_matches(actual, expected, pieces, precision, precision))

    def test_site_with_three_decimal_places(self):
        # 0.5 / 3 -> 0.167; native stock is 0.501 kg, not exactly 0.5.
        self.assertTrue(stock_weight_matches(0.501, 0.5, 3, 3, 3))
        self.assertTrue(stock_weight_matches(1.002, 1, 6, 3, 3))
        # Confirming a different packed weight keeps the same conversion rules.
        self.assertTrue(stock_weight_matches(0.549, 0.55, 3, 3, 3))
        self.assertFalse(stock_weight_matches(0.503, 0.5, 3, 3, 3))


class TestPreweighedPacking(unittest.TestCase):
    def test_fixed_weight_lines_cannot_be_repriced_by_packing(self):
        lines = [{"option_id": "530g", "preweighed": True}, {"option_id": "legacy"}]
        self.assertEqual(packed_weights(lines, {"1": 0.6}), {1: 0.6})
        with self.assertRaises(ValueError):
            packed_weights(lines, {"0": 0.7, "1": 0.6})
