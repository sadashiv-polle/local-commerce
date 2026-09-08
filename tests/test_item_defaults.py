"""Exercise the creation-only default filter without a Bench database."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class Row(dict):
    @property
    def company(self):
        return self["company"]

    def set(self, key, value):
        self[key] = value


class ItemDefaultTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        scope = Mock()
        path = Path(__file__).resolve().parents[1] / "local_commerce/services/products.py"
        spec = importlib.util.spec_from_file_location("lc_products_under_test", path)
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(
            sys.modules, {"frappe": self.frappe, "local_commerce.permissions.scope": scope}
        ):
            spec.loader.exec_module(self.module)
        self.frappe.db.get_value.side_effect = lambda dt, name, field: (
            "A" if dt == "LC Shop" or name == "own" else "B"
        )

    def run_filter(self, row, authorized=True):
        doc = SimpleNamespace(lc_shop="shop-a", item_defaults=[row], is_new=lambda: True)
        token = self.module._item_creation.set(authorized)
        try:
            self.module.scope_creation_defaults(doc)
        finally:
            self.module._item_creation.reset(token)

    def test_discards_foreign_warehouse_and_account_but_keeps_own_defaults(self):
        row = Row(
            company="A",
            default_warehouse="foreign",
            income_account="foreign",
            expense_account="own",
            buying_cost_center="foreign",
        )
        self.run_filter(row)
        self.assertIsNone(row["default_warehouse"])
        self.assertIsNone(row["income_account"])
        self.assertIsNone(row["buying_cost_center"])
        self.assertEqual(row["expense_account"], "own")
        self.assertEqual(row.company, "A")

    def test_does_not_change_standard_erpnext_creation(self):
        row = Row(company="A", default_warehouse="foreign")
        self.run_filter(row, authorized=False)
        self.assertEqual(row["default_warehouse"], "foreign")
        self.frappe.db.get_value.assert_not_called()

    def test_valid_warehouse_is_preserved(self):
        row = Row(company="A", default_warehouse="own")
        self.run_filter(row)
        self.assertEqual(row["default_warehouse"], "own")
