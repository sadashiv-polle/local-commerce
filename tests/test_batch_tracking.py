"""Exercise the production GPS handler with an in-memory order store."""

import ast
import unittest
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from local_commerce.services.location_rules import accuracy_metres, point


class Record(SimpleNamespace):
    def get(self, key):
        return getattr(self, key, None)

    def reload(self):
        pass

    def save(self, **kwargs):
        self.saved = True


class TestBatchTracking(unittest.TestCase):
    def setUp(self):
        self.rows = {}
        for name, slot, user, status in [
            ("anchor", "batch", "rider", "Out for Delivery"),
            ("second", "batch", "rider", "Out for Delivery"),
            ("other-rider", "batch", "other", "Out for Delivery"),
            ("other-batch", "elsewhere", "rider", "Out for Delivery"),
            ("finished", "batch", "rider", "Delivered"),
            ("not-started", "batch", "rider", "Ready"),
        ]:
            self.rows[name] = Record(
                name=name,
                shop="shop",
                scheduled_slot=slot,
                delivery_user=user,
                status=status,
                delivery_mode="Scheduled",
                customer_user=name + "@test",
                driver_location_at=None,
                saved=False,
            )
        self.frappe = Mock()
        self.frappe.session.user = "rider"
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = PermissionError
        self.frappe.get_doc.side_effect = lambda dt, name: (
            Record(live_tracking_enabled=1) if dt == "LC Shop" else self.rows[name]
        )
        self.frappe.get_all.side_effect = lambda dt, filters, **kwargs: [
            row.name
            for row in self.rows.values()
            if all(row.get(key) == value for key, value in filters.items())
        ]

        def reject(message):
            raise ValueError(message)

        namespace = {
            "frappe": self.frappe,
            "is_shop_driver": lambda *args: True,
            "reject": reject,
            "point": point,
            "accuracy_metres": accuracy_metres,
            "now_datetime": lambda: datetime(2026, 9, 22, 10),
            "time_diff_in_seconds": lambda a, b: (a - b).total_seconds(),
            "_order_operation": ContextVar("tracking_test", default=False),
        }
        source = Path("local_commerce/services/orders.py").read_text()
        node = next(
            n
            for n in ast.parse(source).body
            if isinstance(n, ast.FunctionDef) and n.name == "update_driver_location"
        )
        exec(compile(ast.Module(body=[node], type_ignores=[]), "orders.py", "exec"), namespace)
        self.update = namespace["update_driver_location"]

    def test_one_position_reaches_only_own_active_batch_orders(self):
        result = self.update("anchor", 15.5, 73.8, 12)
        self.assertEqual(set(result["orders"]), {"anchor", "second"})
        self.assertEqual({n for n, r in self.rows.items() if r.saved}, {"anchor", "second"})
        recipients = {c.kwargs["user"] for c in self.frappe.publish_realtime.call_args_list}
        self.assertEqual(recipients, {"anchor@test", "second@test"})
        for call in self.frappe.publish_realtime.call_args_list:
            self.assertTrue(call.kwargs["after_commit"])

    def test_completed_anchor_keeps_remaining_customer_tracking(self):
        self.rows["anchor"].status = "Delivered"
        self.assertEqual(self.update("anchor", 15.5, 73.8, 12)["orders"], ["second"])
        self.assertFalse(self.rows["anchor"].saved)
        self.rows["second"].status = "Delivered"
        self.assertTrue(self.update("anchor", 15.5, 73.8, 12)["tracking_complete"])

    def test_throttle_is_per_order_and_normal_delivery_stays_separate(self):
        self.rows["anchor"].driver_location_at = datetime(2026, 9, 22, 9, 59, 55)
        self.assertEqual(self.update("anchor", 15.5, 73.8, 12)["orders"], ["second"])
        self.rows["anchor"].scheduled_slot = None
        self.rows["anchor"].driver_location_at = None
        self.assertEqual(self.update("anchor", 15.5, 73.8, 12)["orders"], ["anchor"])

    def test_unassigned_rider_cannot_publish(self):
        with self.assertRaises(PermissionError):
            self.update("other-rider", 15.5, 73.8, 12)
        self.frappe.publish_realtime.assert_not_called()
