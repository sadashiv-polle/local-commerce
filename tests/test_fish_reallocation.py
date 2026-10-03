"""Exercise reservation refresh with real allocation and validation functions."""

import ast
import json
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from local_commerce.services import fish_rules


class Row(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class FishReallocationTests(unittest.TestCase):
    def setUp(self):
        now = datetime(2026, 10, 3, 12)
        self.old = Row(
            name="old",
            shop="shop",
            warehouse="warehouse",
            item="fish",
            remaining=2,
            expires_at=now - timedelta(days=1),
        )
        self.fresh = Row(self.old, name="fresh", remaining=17, expires_at=now + timedelta(days=1))
        self.order = Row(
            name="order",
            shop="shop",
            sales_order="so",
            scheduled_slot="slot",
            fish_allocations_json=json.dumps([dict(lot="old", item="fish", quantity=1)]),
        )
        self.shop = Row(name="shop", warehouse="warehouse")
        self.so = SimpleNamespace(items=[Row(item_code="fish", stock_uom="Nos", stock_qty=1)])
        frappe = Mock()
        frappe.get_doc.side_effect = lambda kind, name: {
            "LC Shop": self.shop,
            "Sales Order": self.so,
            "LC Fish Lot": {"old": self.old, "fresh": self.fresh}.get(name),
        }[kind]
        frappe.db.get_value.side_effect = lambda kind, *args: (
            "Nos" if kind == "Item" else now - timedelta(days=2)
        )

        def reject(message):
            raise ValueError(message)

        self.scope = dict(
            frappe=frappe,
            json=json,
            Decimal=Decimal,
            fish_rules=fish_rules,
            enabled=lambda shop: True,
            now_datetime=lambda: now,
            get_datetime=lambda value: value,
            reject=reject,
            reservations=Mock(return_value={}),
            lots=Mock(return_value=[self.old, self.fresh]),
        )
        source = ast.parse(Path("local_commerce/services/fish.py").read_text())
        source.body = [
            node
            for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name in {"reserve", "validate_order"}
        ]
        exec(compile(source, "fish.py", "exec"), self.scope)

    def test_ready_replaces_expired_reservation_even_for_past_delivery_slot(self):
        self.scope["validate_order"](self.order, refresh_expired=True)
        self.assertEqual(
            json.loads(self.order.fish_allocations_json),
            [dict(lot="fresh", item="fish", quantity=1.0)],
        )
        self.assertEqual(self.fresh.remaining, 17)
        self.scope["reservations"].assert_called_once_with(self.shop, exclude_order="order")

    def test_other_orders_reservations_cannot_be_taken(self):
        self.scope["reservations"].return_value = {"fresh": Decimal(17)}
        before = self.order.fish_allocations_json
        with self.assertRaisesRegex(ValueError, "Not enough unexpired"):
            self.scope["validate_order"](self.order, refresh_expired=True)
        self.assertEqual(self.order.fish_allocations_json, before)

    def test_dispatch_still_rejects_expired_stock(self):
        with self.assertRaisesRegex(ValueError, "Reserved fish stock expired"):
            self.scope["validate_order"](self.order)

    def test_valid_reservation_is_unchanged(self):
        self.old.expires_at = self.fresh.expires_at
        before = self.order.fish_allocations_json
        self.scope["validate_order"](self.order, refresh_expired=True)
        self.assertEqual(self.order.fish_allocations_json, before)
        self.scope["reservations"].assert_not_called()
