import unittest
from datetime import datetime
from types import SimpleNamespace

from local_commerce.services.shop_hours import DAYS, availability, normalize


def schedule(opens="09:00", closes="21:00"):
    return [
        {"day": day, "enabled": True, "opens": opens, "closes": closes} for day in DAYS
    ]


class ShopHoursTests(unittest.TestCase):
    def test_open_closing_soon_and_next_opening(self):
        doc = SimpleNamespace(accepting_orders=1, opening_hours_json=schedule())
        self.assertEqual(availability(doc, datetime(2026, 9, 16, 12))["label"], "Open")
        self.assertEqual(
            availability(doc, datetime(2026, 9, 16, 20, 45))["label"], "Closing soon"
        )
        closed = availability(doc, datetime(2026, 9, 16, 22))
        self.assertFalse(closed["open"])
        self.assertIn("tomorrow", closed["message"])

    def test_manual_pause_and_overnight_schedule(self):
        paused = SimpleNamespace(accepting_orders=0, opening_hours_json=schedule())
        self.assertEqual(availability(paused, datetime(2026, 9, 16, 12))["label"], "Paused")
        overnight = SimpleNamespace(
            accepting_orders=1, opening_hours_json=schedule("18:00", "02:00")
        )
        self.assertTrue(availability(overnight, datetime(2026, 9, 16, 23))["open"])
        self.assertTrue(availability(overnight, datetime(2026, 9, 17, 1))["open"])

    def test_schedule_requires_all_days_and_valid_times(self):
        with self.assertRaisesRegex(ValueError, "seven days"):
            normalize(schedule()[:6])
        invalid = schedule()
        invalid[0]["opens"] = "25:00"
        with self.assertRaisesRegex(ValueError, "valid time"):
            normalize(invalid)


if __name__ == "__main__":
    unittest.main()
