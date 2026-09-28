import ast
import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


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

        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute(
            "create table `tabLC Order` (name, customer_user, status, payment_status, "
            "gateway_accounting_error, shop, sales_order, creation)"
        )
        self.db.execute("create table `tabLC Shop` (name, shop_name)")
        self.db.execute("create table `tabSales Order Item` (parent, item_name)")
        self.db.execute("insert into `tabLC Shop` values ('shop', 'Fish World')")
        for index, row in enumerate(self.rows):
            self.db.execute(
                "insert into `tabLC Order` values (?, ?, ?, 'Pending', '', 'shop', ?, ?)",
                (row["name"], row["customer_user"], row["status"], row["name"], index),
            )
        self.db.executemany(
            "insert into `tabLC Order` values (?, 'customer', 'Requested', ?, ?, 'shop', '', 99)",
            [
                ("failed", "Failed", ""),
                ("review", "Paid", "Stock review"),
                ("refund", "Refunded", ""),
            ],
        )
        self.db.executemany(
            "insert into `tabSales Order Item` values ('pending', ?)",
            [("Kingfish",), ("Kingfish",)],
        )
        self.rows.extend(
            dict(name=name, customer_user="customer", status="Requested")
            for name in ["failed", "review", "refund"]
        )

        def sql(query, values, as_dict=False, pluck=False):
            cursor = self.db.execute(query.replace("%s", "?"), values)
            rows = cursor.fetchall()
            if pluck:
                return [row[0] for row in rows]
            if not as_dict:
                return rows
            return [
                SimpleNamespace(**dict(zip([c[0] for c in cursor.description], row)))
                for row in rows
            ]

        self.frappe.db.sql.side_effect = sql
        spec = importlib.util.spec_from_file_location(
            "local_commerce.services.customer_orders",
            Path(__file__).resolve().parents[1] / "local_commerce/services/customer_orders.py",
        )
        module = importlib.util.module_from_spec(spec)
        modules = patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "local_commerce.services.owner": SimpleNamespace(reject=reject),
                "local_commerce.services.customer_orders": module,
            },
        )
        modules.start()
        self.addCleanup(modules.stop)
        spec.loader.exec_module(module)

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

    def test_filter_precedes_pagination_and_excludes_failed_and_cancelled_orders(self):
        result = self.list_orders(customer_view="pending")
        self.assertEqual([row["name"] for row in result["orders"]], ["pending"])
        self.assertEqual(
            result["counts"], {"pending": 1, "delivered": 25, "attention": 3, "cancelled": 1}
        )

    def test_attention_preserves_payment_disputes_but_excludes_cancellations(self):
        result = self.list_orders(customer_view="attention")
        self.assertEqual({row["name"] for row in result["orders"]}, {"failed", "review", "refund"})

    def test_product_search_does_not_duplicate_orders(self):
        result = self.list_orders(customer_view="pending", search="Kingfish", status="Preparing")
        self.assertEqual([row["name"] for row in result["orders"]], ["pending"])
        self.assertEqual(result["counts"]["pending"], 1)
        self.assertEqual(result["total"], 1)

    def test_tab_totals_stay_constant_when_filter_has_no_matches(self):
        unfiltered = self.list_orders(customer_view="pending")
        filtered = self.list_orders(customer_view="pending", status="Ready", search="Kingfish")
        self.assertEqual(filtered["counts"], unfiltered["counts"])
        self.assertEqual(filtered["orders"], [])
        self.assertEqual(filtered["total"], 0)

    def test_filtered_pagination_uses_matching_total_not_tab_total(self):
        result = self.list_orders(customer_view="delivered", search="24")
        self.assertEqual(result["counts"]["delivered"], 25)
        self.assertEqual(result["total"], 1)
        self.assertEqual([row["name"] for row in result["orders"]], ["24"])

    def test_cancelled_payment_issue_stays_in_cancelled_history(self):
        self.db.execute(
            "update `tabLC Order` set payment_status='Failed', "
            "gateway_accounting_error='Needs review' where name='cancelled'"
        )
        result = self.list_orders(customer_view="cancelled", search="cancelled")
        self.assertEqual([row["name"] for row in result["orders"]], ["cancelled"])
        self.assertEqual(result["counts"]["attention"], 3)
        self.assertEqual(result["total"], 1)

    def test_search_by_shop_or_partial_order_id(self):
        self.assertEqual(
            len(self.list_orders(customer_view="delivered", search="Fish World")["orders"]), 20
        )
        self.assertEqual(
            self.list_orders(customer_view="pending", search="pend")["orders"][0]["name"], "pending"
        )

    def test_search_is_parameterized_and_scoped_to_customer(self):
        for search in ["%' OR 1=1 --", "private", "%"]:
            self.assertFalse(self.list_orders(customer_view="delivered", search=search)["orders"])

    def test_successful_reverification_returns_failed_order_to_active(self):
        self.db.execute(
            "update `tabLC Order` set payment_status='Paid', status='Accepted' where name='failed'"
        )
        result = self.list_orders(customer_view="pending")
        self.assertIn("failed", [row["name"] for row in result["orders"]])
        self.assertEqual(result["counts"]["attention"], 2)

    def test_invalid_status_and_search_are_rejected_before_query(self):
        for kwargs in ({"status": "invented"}, {"search": "x" * 101}):
            with self.assertRaises(ValueError):
                self.list_orders(customer_view="pending", **kwargs)
        self.frappe.db.sql.assert_not_called()

    def test_delivered_orders_remain_in_history_even_if_later_refunded(self):
        self.db.execute("update `tabLC Order` set payment_status='Refunded' where name='0'")
        result = self.list_orders(customer_view="delivered", search="0")
        self.assertIn("0", [row["name"] for row in result["orders"]])

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
