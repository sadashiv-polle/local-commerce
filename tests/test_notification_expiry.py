import unittest
from datetime import datetime, timedelta
from local_commerce.services.notification_expiry import expires_at
from local_commerce.services.shop_hours import DAYS


class NotificationExpiryTests(unittest.TestCase):
    def schedule(self, opens='09:00', closes='21:00'):
        return [dict(day=day, enabled=True, opens=opens, closes=closes) for day in DAYS]

    def test_ten_hours_without_schedule(self):
        created = datetime(2026, 11, 5, 10)
        self.assertEqual(expires_at(created), created + timedelta(hours=10))

    def test_earlier_of_ten_hours_and_closing(self):
        self.assertEqual(expires_at(datetime(2026, 11, 5, 9), self.schedule()), datetime(2026, 11, 5, 19))
        self.assertEqual(expires_at(datetime(2026, 11, 5, 18), self.schedule()), datetime(2026, 11, 5, 21))

    def test_overnight_closing(self):
        for created in [datetime(2026, 11, 5, 23), datetime(2026, 11, 6, 1)]:
            self.assertEqual(expires_at(created, self.schedule('20:00', '02:00')), datetime(2026, 11, 6, 2))

    def test_after_closing_app_message_gets_ten_hours(self):
        created = datetime(2026, 11, 5, 22)
        self.assertEqual(expires_at(created, self.schedule()), created + timedelta(hours=10))
