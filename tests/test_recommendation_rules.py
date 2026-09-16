import unittest
from datetime import date, timedelta

from local_commerce.services.recommendation_rules import rank_products


class RecommendationTests(unittest.TestCase):
    today = date(2026, 9, 17)

    def purchase(self, item, age, order=None):
        return {"item": item, "order": order or f"{item}-{age}",
                "purchased_on": self.today - timedelta(days=age)}

    def test_same_weekday_boosts_regular_purchase(self):
        rows = [self.purchase("fish", 7), self.purchase("rice", 1)]
        self.assertEqual(rank_products(rows, self.today), ["fish", "rice"])

    def test_old_habits_fade_and_out_of_window_is_ignored(self):
        rows = [self.purchase("old", 150), self.purchase("new", 1),
                self.purchase("expired", 181), self.purchase("future", -1)]
        self.assertEqual(rank_products(rows, self.today), ["new", "old"])

    def test_duplicate_order_lines_do_not_inflate_frequency(self):
        rows = [self.purchase("fish", 2, "one")] * 10
        rows += [self.purchase("rice", 2, "two"), self.purchase("rice", 3, "three")]
        self.assertEqual(rank_products(rows, self.today), ["rice", "fish"])

    def test_new_customer_has_no_personal_picks(self):
        self.assertEqual(rank_products([], self.today), [])
