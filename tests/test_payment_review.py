import importlib.util
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class PaymentReviewTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.whitelist.return_value = lambda function: function
        self.guard = Mock()
        self.reject = Mock(side_effect=ValueError)
        self.frappe.get_all.return_value = []
        with patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "local_commerce.permissions.scope": SimpleNamespace(require_shop=self.guard),
                "local_commerce.services.orders": SimpleNamespace(
                    offset=int, serialize=lambda doc: doc
                ),
                "local_commerce.services.owner": SimpleNamespace(reject=self.reject),
            },
        ):
            spec = importlib.util.spec_from_file_location(
                "review_test", "local_commerce/api/payment_review.py"
            )
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

    def test_access_denied_before_read(self):
        self.guard.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.module.list_orders("foreign-shop")
        self.frappe.get_all.assert_not_called()

    def test_all_queues_are_scoped_to_shop(self):
        for category in ["upi", "cashfree", "accounting", "refunds"]:
            self.module.list_orders("shop", category)
            self.guard.assert_called_with("shop", "write")
            self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"]["shop"], "shop")
        self.assertEqual(
            self.frappe.get_all.call_args.kwargs["filters"]["gateway_refunded_amount"], [">", 0]
        )

    def test_invalid_queue_rejected(self):
        with self.assertRaises(ValueError):
            self.module.list_orders("shop", "invalid")
        self.frappe.get_all.assert_not_called()

    def test_pagination_serializes_only_twenty_orders(self):
        self.frappe.get_all.return_value = list(range(21))
        result = self.module.list_orders("shop", start=20)
        self.assertTrue(result["has_more"])
        self.assertEqual(len(result["orders"]), 20)
        self.assertEqual(self.frappe.get_doc.call_count, 20)
        self.assertEqual(self.frappe.get_all.call_args.kwargs["start"], 20)
