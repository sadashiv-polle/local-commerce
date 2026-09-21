import unittest

from local_commerce.services.schedule_rules import nearest_stops, window


class TestScheduleRules(unittest.TestCase):
    def test_window_crossing_midnight(self):
        result = window(
            "2026-09-21 18:00", "2026-09-22 06:00", "2026-09-22 08:00", "2026-09-22 10:00"
        )
        self.assertLess(result[0], result[1])
        for values in [
            ("2026-09-21 08:00", "2026-09-21 07:00", "2026-09-21 09:00", "2026-09-21 10:00"),
            ("2026-09-21 06:00", "2026-09-21 09:00", "2026-09-21 08:00", "2026-09-21 10:00"),
        ]:
            with self.assertRaises(ValueError):
                window(*values)

    def test_sequence_uses_asymmetric_road_times(self):
        matrix = [[0, 30, 10, 20], [12, 0, 5, 2], [8, 50, 0, 4], [3, 1, 2, 0]]
        self.assertEqual(nearest_stops(matrix), [1, 2, 0])
        self.assertEqual(nearest_stops([[0, 1], [2, 0]]), [0])

    def test_unreachable_stops_are_not_claimed_to_be_routed(self):
        with self.assertRaises(ValueError):
            nearest_stops([[0, None], [None, 0]])
        with self.assertRaises(ValueError):
            nearest_stops([[0, float("nan")], [1, 0]])
