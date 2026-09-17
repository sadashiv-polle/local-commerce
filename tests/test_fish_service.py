"""Verify the fish-only service boundary and shared-stock reservation contract."""

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from local_commerce.services.owner_rules import number


class Row(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


class TestFishService(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 9)
        self.shop = Row(name='shop', shop_type='Fish', warehouse='W')
        self.frappe = Mock()
        utilities = Mock(now_datetime=lambda: self.now, get_datetime=lambda value: value)
        owner = Mock(checked_number=number, reject=Mock(side_effect=ValueError))
        path = Path(__file__).resolve().parents[1] / 'local_commerce/services/fish.py'
        spec = importlib.util.spec_from_file_location('lc_fish_under_test', path)
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'frappe': self.frappe, 'frappe.utils': utilities,
                                     'local_commerce.permissions.scope': Mock(),
                                     'local_commerce.services.owner': owner}):
            spec.loader.exec_module(self.module)
        self.frappe.get_doc.return_value = self.shop
        self.module.lots = Mock(return_value=[Row(
            name='lot', item='fish', remaining=10, expires_at=self.now + timedelta(hours=1))])
        self.module.reservations = Mock(return_value={})

    def test_fish_only_default_offer_requires_packing_without_changing_other_shops(self):
        fish = Row(stock_uom='Kg')
        default = self.module.selling_options(self.shop, fish, [])
        self.assertEqual(default[0]['billing'], 'Weight')
        self.assertEqual(default[0]['kind'], 'Weight')
        self.assertEqual(self.module.selling_options(Row(shop_type='General'), fish, []), [])
        self.assertEqual(self.module.selling_options(self.shop, Row(stock_uom='Nos'), []), [])
        configured = [{'id': 'count', 'kind': 'Count', 'billing': 'Pieces'}]
        self.assertIs(self.module.selling_options(self.shop, fish, configured), configured)

    def test_sellable_excludes_expired_reserved_stock_and_respects_native_balance(self):
        item = Row(name='fish', stock_uom='Kg')
        self.module.reservations.return_value = {'lot': 8}
        self.assertEqual(self.module.sellable(self.shop, item, 5), 2)
        self.assertEqual(self.module.sellable(self.shop, item, 1), 1)
        self.module.lots.return_value[0]['expires_at'] = self.now
        self.assertEqual(self.module.sellable(self.shop, item, 5), 0)
        self.assertEqual(self.module.sellable(Row(shop_type='General'), item, 5), 5)

    def test_reservation_uses_native_stock_kg_and_excludes_the_order_being_repacked(self):
        self.frappe.db.get_value.side_effect = lambda dt, item, field: (
            'Kg' if item == 'fish' else 'Nos')
        self.module.reservations.return_value = {'lot': 5}
        order = Row(name='order', shop='shop')
        rows = [Row(item_code='fish', stock_qty=1.2), Row(item_code='fish', stock_qty=0.5),
                Row(item_code='other', stock_qty=100)]
        self.module.reserve(order, rows)
        self.assertEqual(json.loads(order.fish_allocations_json),
                         [{'lot': 'lot', 'item': 'fish', 'quantity': 1.7}])
        self.module.reservations.assert_called_once_with(self.shop, exclude_order='order')
        with self.assertRaises(ValueError):
            self.module.reserve(order, [Row(item_code='fish', stock_qty=6)])

    def test_order_validation_blocks_expired_reserved_lots_before_dispatch(self):
        lot = Row(shop='shop', warehouse='W', item='fish', remaining=10,
                  expires_at=self.now - timedelta(seconds=1))
        so = SimpleNamespace(items=[Row(item_code='fish', stock_uom='Kg', stock_qty=0.8)])
        self.frappe.get_doc.side_effect = lambda dt, name: {
            'LC Shop': self.shop, 'Sales Order': so, 'LC Fish Lot': lot}[dt]
        parts = [{'lot': 'lot', 'item': 'fish', 'quantity': 0.8}]
        order = Row(shop='shop', sales_order='SO', fish_allocations_json=json.dumps(parts))
        with self.assertRaises(ValueError):
            self.module.validate_order(order)
        lot['expires_at'] = self.now + timedelta(hours=1)
        self.module.validate_order(order)
