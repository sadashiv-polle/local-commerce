import unittest

from local_commerce.services.location_rules import accuracy_metres, delivery_match, distance_km, point


class LocationRulesTests(unittest.TestCase):
    def test_browser_accuracy_accepts_extra_decimal_places(self):
        self.assertEqual(accuracy_metres(12.3456789012345), 12.346)
        self.assertEqual(accuracy_metres(0.000000123), 0)
        self.assertEqual(accuracy_metres(5000), 5000)

    def test_accuracy_rejects_invalid_or_over_limit_measurements(self):
        for value in ["NaN", "Infinity", -1, 5000.0000001, "invalid", ""]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                accuracy_metres(value)

    def test_point_accepts_signed_coordinates_and_uses_schema_precision(self):
        self.assertEqual(
            point("15.49888888", "-73.82777777", required=True),
            {"latitude": 15.498889, "longitude": -73.827778},
        )

    def test_point_requires_both_coordinates_and_valid_ranges(self):
        self.assertIsNone(point(None, ""))
        for latitude, longitude in [("15", ""), (91, 20), (20, -181), ("NaN", 10)]:
            with (
                self.subTest(latitude=latitude, longitude=longitude),
                self.assertRaises(ValueError),
            ):
                point(latitude, longitude, required=True)

    def test_distance_uses_great_circle_calculation(self):
        distance = distance_km(
            {"latitude": 15.4909, "longitude": 73.8278},
            {"latitude": 15.4989, "longitude": 73.8278},
        )
        self.assertAlmostEqual(distance, 0.89, places=2)

    def test_nearby_match_uses_delivery_radius(self):
        origin = {"latitude": 15.4909, "longitude": 73.8278}
        destination = {"latitude": 15.4989, "longitude": 73.8278}
        available = delivery_match(origin, destination, 2)
        self.assertTrue(available["serviceable"])
        self.assertEqual(available["message"], "Delivers to this address")
        self.assertFalse(
            delivery_match(origin, destination, 0.5)["serviceable"]
        )
        self.assertEqual(
            delivery_match(origin, destination, 0.5)["message"],
            "Outside delivery radius",
        )


if __name__ == "__main__":
    unittest.main()
