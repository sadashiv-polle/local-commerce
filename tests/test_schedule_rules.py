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


class TestBatchTransitions(unittest.TestCase):
    def test_each_stage_and_safe_retries(self):
        from local_commerce.services.schedule_rules import batch_transition

        for source, target in [
            ("Accepted", "Preparing"),
            ("Preparing", "Ready"),
            ("Ready", "Picked Up"),
            ("Picked Up", "Out for Delivery"),
        ]:
            rows = [
                {"name": "a", "status": source},
                {"name": "b", "status": target},
                {"name": "cancelled", "status": "Cancelled"},
            ]
            self.assertEqual(batch_transition(rows, target), ["a"])
            rows[0]["status"] = target
            self.assertEqual(batch_transition(rows, target), [])

    def test_individual_acceptance_and_delivery_are_required(self):
        from local_commerce.services.schedule_rules import batch_transition

        for target in ["Accepted", "Delivered", "Cancelled"]:
            with self.assertRaises(ValueError):
                batch_transition([], target)
        for target in ["Preparing", "Ready", "Picked Up", "Out for Delivery"]:
            with self.assertRaises(ValueError):
                batch_transition([{"name": "unaccepted", "status": "Requested"}], target)
        with self.assertRaises(ValueError):
            batch_transition([{"name": "a", "status": "Accepted"}], "Ready")
