import importlib.util
import sys
import unittest
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class ArrivalTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.session.user = "driver"
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = lambda message, kind: (_ for _ in ()).throw(kind(message))
        self.orders, self.notifications = Mock(), Mock()
        self.orders._order_operation = ContextVar("arrival_test", default=False)
        self.orders.is_shop_driver.return_value = True
        owner = Mock()
        owner.reject.side_effect = ValueError
        modules = patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "frappe.utils": SimpleNamespace(now_datetime=lambda: "2026-09-27 12:00:00"),
                "local_commerce.services.orders": self.orders,
                "local_commerce.services.notifications": self.notifications,
                "local_commerce.services.owner": owner,
            },
        )
        modules.start()
        self.addCleanup(modules.stop)
        spec = importlib.util.spec_from_file_location(
            "arrival_test",
            Path(__file__).resolve().parents[1] / "local_commerce/services/delivery_arrival.py",
        )
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.doc = SimpleNamespace(
            name="order1",
            shop="shop1",
            delivery_user="driver",
            customer_user="customer1",
            status="Out for Delivery",
            arrived_at=None,
            save=Mock(),
            reload=Mock(),
        )
        self.doc.get = lambda key: getattr(self.doc, key, None)
        self.frappe.get_doc.return_value = self.doc

    def test_arrival_notifies_once_without_completing_delivery(self):
        self.service.mark_arrived("order1")
        self.service.mark_arrived("order1")
        self.notifications.delivery_arrived.assert_called_once_with(self.doc)
        self.doc.save.assert_called_once()
        self.assertEqual(self.doc.status, "Out for Delivery")
        self.assertEqual(self.doc.arrived_by, "driver")
        self.assertFalse(self.orders._order_operation.get())

    def test_other_driver_is_denied(self):
        self.frappe.session.user = "other"
        with self.assertRaises(PermissionError):
            self.service.mark_arrived("order1")
        self.notifications.delivery_arrived.assert_not_called()

    def test_reassignment_while_waiting_for_lock_is_denied(self):
        self.doc.reload.side_effect = lambda: setattr(self.doc, "delivery_user", "other")
        with self.assertRaises(PermissionError):
            self.service.mark_arrived("order1")
        self.doc.save.assert_not_called()

    def test_arrival_requires_active_delivery(self):
        for status in ["Requested", "Ready", "Picked Up", "Delivered", "Cancelled"]:
            self.doc.status = status
            with self.assertRaises(ValueError):
                self.service.mark_arrived("order1")
        self.notifications.delivery_arrived.assert_not_called()


if __name__ == "__main__":
    unittest.main()
