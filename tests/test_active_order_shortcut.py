import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


class TestActiveOrderShortcut(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] /
                          "local_commerce/services/orders.py").read_text())
        function = next(n for n in tree.body
                        if isinstance(n, ast.FunctionDef) and n.name == "active_orders")
        self.frappe = Mock()
        self.frappe.session.user = "customer@example.com"
        self.frappe.get_all.return_value = [
            {"name": "order-1", "shop": "shop-1", "status": "Preparing"}
        ]
        self.frappe.db.get_value.return_value = "Fish World"
        self.access = Mock()
        scope = {"frappe": self.frappe, "customer_access": self.access}
        module = ast.Module(body=[function], type_ignores=[])
        exec(compile(module, "<active orders>", "exec"), scope)
        self.active_orders = scope["active_orders"]

    def test_scoped_active_query_and_shop_name(self):
        rows = self.active_orders()
        self.access.assert_called_once()
        query = self.frappe.get_all.call_args.kwargs
        self.assertEqual(query["filters"]["customer_user"], "customer@example.com")
        states = query["filters"]["status"][1]
        self.assertIn("Requested", states)
        self.assertIn("Out for Delivery", states)
        self.assertNotIn("Delivered", states)
        self.assertNotIn("Cancelled", states)
        self.assertNotIn("delivery_mode", query["filters"])
        self.assertEqual(query["limit_page_length"], 5)
        self.assertEqual(rows[0]["shop_name"], "Fish World")

    def test_denied_customer_cannot_query_orders(self):
        self.access.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.active_orders()
        self.frappe.get_all.assert_not_called()
