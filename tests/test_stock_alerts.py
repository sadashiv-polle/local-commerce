import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class StockAlertTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.session.user = "customer"
        self.frappe.PermissionError = PermissionError
        self.frappe.ValidationError = ValueError
        self.frappe.DoesNotExistError = LookupError
        self.frappe.throw.side_effect = PermissionError
        owner = Mock()
        owner.reject.side_effect = ValueError
        self.orders = Mock()
        self.orders.public_product.return_value = {"available": 0, "rate": 10}
        import local_commerce.services as services

        scope = patch.object(services, "orders", self.orders, create=True)
        scope.start()
        self.addCleanup(scope.stop)
        modules = patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "frappe.utils": SimpleNamespace(now_datetime=lambda: "now"),
                "local_commerce.services.owner": owner,
                "local_commerce.services.orders": self.orders,
            },
        )
        modules.start()
        self.addCleanup(modules.stop)
        spec = importlib.util.spec_from_file_location(
            "stock_alerts_test", Path("local_commerce/services/stock_alerts.py")
        )
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.row = SimpleNamespace(user="customer", shop="shop", item="item")
        self.frappe.get_doc.return_value = self.row
        self.frappe.db.sql.return_value = [("subscription",)]
        self.frappe.db.get_value.return_value = 1
        self.real_notify = self.service.notify
        self.service.notify = Mock()

    def test_notification_targets_subscriber_and_enqueues_after_commit(self):
        from contextvars import ContextVar

        operation = ContextVar("notification_test", default=False)
        notification = Mock(name="notification")
        self.frappe.get_doc.return_value = Mock()
        self.frappe.get_doc.return_value.insert.return_value = notification
        with patch.dict(
            sys.modules,
            {
                "local_commerce.services.notifications": SimpleNamespace(
                    _notification_operation=operation
                )
            },
        ):
            self.real_notify(self.row, {"item_name": "Mackerel"})
        payload = self.frappe.get_doc.call_args.args[0]
        self.assertEqual(payload["recipient_user"], "customer")
        self.assertEqual(payload["target"], "/store/shop?item=item")
        self.assertEqual(payload["item"], "item")
        self.assertFalse(operation.get())
        self.assertTrue(self.frappe.enqueue.call_args.kwargs["enqueue_after_commit"])

    def test_sold_out_stock_is_retained_and_rechecked(self):
        self.service.process_one("subscription")
        self.service.notify.assert_not_called()
        self.frappe.delete_doc.assert_not_called()
        self.frappe.db.set_value.assert_called_once_with(
            "LC Stock Alert", "subscription", "last_checked", "now"
        )

    def test_restock_is_one_shot_and_cancelled_records_are_not_notified(self):
        self.orders.public_product.return_value = {"available": 4, "rate": 10}
        self.service.process_one("subscription")
        self.service.notify.assert_called_once()
        self.frappe.delete_doc.assert_called_once_with(
            "LC Stock Alert", "subscription", ignore_permissions=True
        )
        self.frappe.db.sql.return_value = []
        self.service.process_one("subscription")
        self.assertEqual(self.service.notify.call_count, 1)

    def test_disabled_customer_does_not_receive_alert(self):
        self.frappe.db.get_value.return_value = 0
        self.service.process_one("subscription")
        self.service.notify.assert_not_called()
        self.orders.public_product.assert_not_called()

    def test_archived_product_is_not_notified(self):
        self.orders.public_product.side_effect = ValueError("unavailable")
        self.service.process_one("subscription")
        self.service.notify.assert_not_called()
        self.frappe.delete_doc.assert_not_called()

    def test_guest_cannot_subscribe(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.service.toggle("shop", "item")
        self.frappe.db.sql.assert_not_called()

    def test_existing_subscription_is_idempotent(self):
        self.frappe.db.exists.return_value = True
        self.assertEqual(self.service.toggle("shop", "item"), {"saved": True})
        self.frappe.get_doc.assert_not_called()

    def test_cancellation_is_scoped_to_logged_in_user(self):
        self.service.toggle("shop", "item", 0)
        self.frappe.delete_doc.assert_called_once_with(
            "LC Stock Alert", self.service.key("customer", "item"), ignore_permissions=True
        )
        self.assertNotEqual(self.service.key("customer", "item"), self.service.key("other", "item"))

    def test_price_and_whole_pack_availability_are_required(self):
        self.assertFalse(self.service.restocked({"available": 10, "rate": None}))
        product = {
            "available": 0.2,
            "rate": 100,
            "selling_options": [{"estimated_weight": 0.5, "billing": "Weight"}],
        }
        self.assertFalse(self.service.restocked(product))
        product["available"] = 0.5
        self.assertTrue(self.service.restocked(product))

    def test_notification_failure_does_not_consume_subscription(self):
        self.orders.public_product.return_value = {"available": 1, "rate": 10}
        self.service.notify.side_effect = RuntimeError("retry")
        with self.assertRaises(RuntimeError):
            self.service.process_one("subscription")
        self.frappe.delete_doc.assert_not_called()
