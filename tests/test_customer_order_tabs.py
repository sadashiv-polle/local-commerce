import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


class CustomerOrderTabsTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_commerce/services/orders.py").read_text()
        )
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "list_orders"
        )
        self.frappe = Mock()
        self.frappe.session.user = "customer"
        self.rows = [
            dict(name=str(i), customer_user="customer", status="Delivered") for i in range(25)
        ]
        self.rows += [
            dict(name="pending", customer_user="customer", status="Preparing"),
            dict(name="cancelled", customer_user="customer", status="Cancelled"),
            dict(name="private", customer_user="other", status="Delivered"),
        ]

        def matches(row, filters):
            return all(
                row[key] != value[1] if isinstance(value, list) else row[key] == value
                for key, value in filters.items()
            )

        self.frappe.get_all.side_effect = lambda _, **kw: [
            row["name"] for row in self.rows if matches(row, kw["filters"])
        ][kw["start"] : kw["start"] + kw["limit_page_length"]]
        self.frappe.db.count.side_effect = lambda _, filters: sum(
            matches(row, filters) for row in self.rows
        )
        self.frappe.get_doc.side_effect = lambda _, name: next(
            row for row in self.rows if row["name"] == name
        )
        self.access = Mock()

        def reject(message):
            raise ValueError(message)

        scope = dict(
            frappe=self.frappe,
            customer_access=self.access,
            require_shop=Mock(),
            offset=int,
            serialize=lambda row: row,
            reject=reject,
        )
        exec(compile(ast.Module(body=[function], type_ignores=[]), "<order tabs>", "exec"), scope)
        self.list_orders = scope["list_orders"]

    def test_filter_precedes_pagination_and_preserves_cancelled_orders(self):
        result = self.list_orders(customer_view="pending")
        self.assertEqual([row["name"] for row in result["orders"]], ["pending", "cancelled"])
        self.assertEqual(result["counts"], {"pending": 2, "delivered": 25})

    def test_delivered_second_page_excludes_other_customers(self):
        result = self.list_orders(customer_view="delivered", start=20)
        self.assertEqual(len(result["orders"]), 5)
        self.assertTrue(all(row["customer_user"] == "customer" for row in result["orders"]))

    def test_legacy_list_response_is_unchanged(self):
        self.assertIsInstance(self.list_orders(), list)
        self.frappe.db.count.assert_not_called()

    def test_unauthorized_customer_cannot_read_counts_or_orders(self):
        self.access.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.list_orders(customer_view="delivered")
        self.frappe.db.count.assert_not_called()
        self.frappe.get_all.assert_not_called()

    def test_customer_filter_is_not_available_for_shop_queries(self):
        with self.assertRaises(ValueError):
            self.list_orders(shop="shop", customer_view="delivered")
        self.frappe.db.count.assert_not_called()
