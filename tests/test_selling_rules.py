import unittest

from local_commerce.services.order_rules import cart_rows
from local_commerce.services.selling_rules import options, packed_weights, selected


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
