"""Regression checks for parameter binding and fixed SQL identifiers in dynamic queries."""

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

PAYLOADS = ["' OR 1=1 --", "x'; DROP TABLE `tabLC Order`; --", "x' UNION SELECT SLEEP(5) --"]


def load_function(path, name, scope):
    tree = ast.parse(Path(path).read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), path, "exec"), scope)
    return scope[name]


def reject(message):
    raise ValueError(message)


class DynamicQuerySafetyTests(unittest.TestCase):
    def setUp(self):
        self.sql = Mock(return_value=[])
        self.authorize = Mock()
        self.listing = load_function(
            "local_commerce/services/admin.py",
            "listing",
            {
                "frappe": SimpleNamespace(db=SimpleNamespace(sql=self.sql)),
                "require_platform": self.authorize,
                "reject": reject,
            },
        )

    def test_admin_search_shop_and_status_remain_bound_values(self):
        for section in ["shops", "orders", "people", "payments"]:
            for payload in PAYLOADS:
                with self.subTest(section=section, payload=payload):
                    self.listing(section, search=payload, shop=payload, status=payload, start=20)
                    query, values = self.sql.call_args.args
                    self.assertNotIn(payload, query)
                    self.assertIn(payload, values)
                    self.assertIn("%" + payload + "%", values)
                    self.assertEqual(values[-1], 20)

    def test_section_cannot_inject_table_or_sort_expressions(self):
        for payload in PAYLOADS:
            with self.assertRaises(ValueError):
                self.listing(payload)
        self.sql.assert_not_called()

    def test_offset_cannot_inject_sql(self):
        for payload in PAYLOADS:
            with self.assertRaises(ValueError):
                self.listing("orders", start=payload)
        self.sql.assert_not_called()

    def test_admin_permission_denial_precedes_queries(self):
        self.authorize.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.listing("orders", search=PAYLOADS[0])
        self.sql.assert_not_called()

    def test_inventory_identifiers_are_bound_even_when_stored_values_look_like_sql(self):
        reservations = load_function(
            "local_commerce/services/owner.py",
            "requested_reservations",
            {
                "frappe": SimpleNamespace(db=SimpleNamespace(sql=self.sql)),
            },
        )
        reservations(PAYLOADS[0], items=[PAYLOADS[1]], exclude_order=PAYLOADS[2])
        query, values = self.sql.call_args.args
        for payload in PAYLOADS:
            self.assertNotIn(payload, query)
        self.assertEqual(values, tuple(PAYLOADS))
