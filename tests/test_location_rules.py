import unittest

from local_commerce.services.location_rules import delivery_match, distance_km, point


class LocationRulesTests(unittest.TestCase):
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

    def test_nearby_match_requires_radius_and_postal_code(self):
        origin = {"latitude": 15.4909, "longitude": 73.8278}
        destination = {"latitude": 15.4989, "longitude": 73.8278}
        available = delivery_match(origin, destination, 2, ["403001"], "403001")
        self.assertTrue(available["serviceable"])
        self.assertEqual(available["message"], "Delivers to this address")
        self.assertFalse(
            delivery_match(origin, destination, 0.5, ["403001"], "403001")["serviceable"]
        )
        self.assertEqual(
            delivery_match(origin, destination, 2, ["403002"], "403001")["message"],
            "Postal code not served",
        )


if __name__ == "__main__":
    unittest.main()
