import unittest

from local_commerce.services.delivery_pricing import delivery_price


class DeliveryPricingTests(unittest.TestCase):
    def test_flat_fee_and_minimum(self):
        result = delivery_price(80, base=20, minimum=100)
        self.assertEqual(result["delivery_fee"], 20)
        self.assertEqual(result["minimum_remaining"], 20)

    def test_distance_charge_and_rounding(self):
        result = delivery_price(100, base=20, per_km=8, included_km=2, distance=4.123)
        self.assertEqual(result["delivery_fee"], 36.98)
        self.assertEqual(
            delivery_price(100, base=20, per_km=8, included_km=2, distance=1)["delivery_fee"], 20
        )

    def test_free_delivery_overrides_distance_charge(self):
        result = delivery_price(300, base=20, per_km=8, free_above=300)
        self.assertEqual(result["delivery_fee"], 0)
        self.assertTrue(result["free_delivery"])
        self.assertFalse(result["needs_location"])
        self.assertEqual(delivery_price(250, free_above=300)["free_delivery_remaining"], 50)

    def test_distance_fee_requires_location(self):
        self.assertTrue(delivery_price(100, per_km=8)["needs_location"])

    def test_negative_config_is_rejected(self):
        with self.assertRaises(ValueError):
            delivery_price(100, base=-1)
