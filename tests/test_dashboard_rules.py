import unittest
from datetime import date

from local_commerce.services.dashboard_rules import period_start


class DashboardPeriodTests(unittest.TestCase):
    def test_calendar_periods(self):
        today = date(2026, 9, 16)
        self.assertEqual(period_start("today", today), today)
        self.assertEqual(period_start("week", today), date(2026, 9, 14))
        self.assertEqual(period_start("month", today), date(2026, 9, 1))
        self.assertEqual(period_start("week", date(2026, 9, 1)), date(2026, 8, 31))

    def test_invalid_period_rejected(self):
        with self.assertRaises(ValueError):
            period_start("all", date(2026, 9, 16))
