import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from local_commerce.services.fish_rules import allocate, expiry


class TestFishRules(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 9)
        self.lots = [
            {'name': 'old', 'item': 'fish', 'remaining': 5,
             'expires_at': self.now - timedelta(minutes=1)},
            {'name': 'later', 'item': 'fish', 'remaining': 5,
             'expires_at': self.now + timedelta(hours=48)},
            {'name': 'first', 'item': 'fish', 'remaining': 2,
             'expires_at': self.now + timedelta(hours=1)},
        ]

    def test_expiry_is_per_receipt_and_supports_fractional_hours(self):
        self.assertEqual(expiry(self.now, 1.5), self.now + timedelta(minutes=90))
        self.assertNotEqual(expiry(self.now, 24), expiry(self.now + timedelta(hours=1), 24))
        for hours in [0, -1, 'NaN', 8761, None]:
            with self.assertRaises(ValueError):
                expiry(self.now, hours)

    def test_earliest_expiry_first_excludes_expired_and_reserved_stock(self):
        self.assertEqual(allocate(self.lots, 4, {'first': Decimal('0.5')}, self.now), [
            {'lot': 'first', 'item': 'fish', 'quantity': 1.5},
            {'lot': 'later', 'item': 'fish', 'quantity': 2.5},
        ])
        with self.assertRaises(ValueError):
            allocate(self.lots, 7, {'first': 0.5}, self.now)

    def test_expiry_boundary_and_over_reservation_never_create_negative_availability(self):
        self.lots[2]['expires_at'] = self.now
        self.assertEqual(allocate(self.lots, 1, {'later': 4}, self.now)[0]['lot'], 'later')
        with self.assertRaises(ValueError):
            allocate(self.lots, 0.1, {'later': 6}, self.now)
        with self.assertRaises(ValueError):
            allocate(self.lots, 0, {}, self.now)
