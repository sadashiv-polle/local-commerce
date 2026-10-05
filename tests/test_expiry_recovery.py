import ast
import json
import unittest
from contextvars import ContextVar
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import hashlib
import sys


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.doc = Mock(name='order')
        self.doc.name = 'order-1'
        self.doc.shop = 'shop'
        self.doc.status = 'Ready'
        self.doc.payment_status = 'Paid'
        self.doc.get.return_value = None
        self.doc.fish_allocations_json = json.dumps([{'lot': 'expired', 'item': 'fish', 'quantity': 2}])
        now = datetime(2026, 10, 5)
        self.frappe = Mock()
        self.frappe.get_doc.side_effect = lambda kind, name: {
            'LC Order': self.doc, 'LC Shop': SimpleNamespace(name='shop'),
            'LC Fish Lot': SimpleNamespace(expires_at=now - timedelta(days=1))}[kind]
        self.fish = Mock(ACTIVE=['Requested', 'Accepted', 'Preparing', 'Ready'])
        self.fish.enabled.return_value = True
        scope = dict(frappe=self.frappe, fish=self.fish, json=json, Decimal=Decimal,
                     hashlib=hashlib, now_datetime=lambda: now, get_datetime=lambda v: v)
        tree = ast.parse(Path('local_commerce/services/expiry_recovery.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        exec(compile(tree, 'expiry_recovery.py', 'exec'), scope)
        self.recover = scope['recover']
        self.module = SimpleNamespace(_order_operation=ContextVar('operation', default=False))

    def test_ready_requires_repacking_and_posts_only_expired_reserved_quantity(self):
        with patch.dict(sys.modules, {'local_commerce.services.orders': self.module}):
            self.assertTrue(self.recover('order-1'))
        self.assertEqual(self.doc.status, 'Preparing')
        self.fish.validate_order.assert_called_once_with(self.doc, refresh_expired=True)
        self.assertEqual(self.fish.adjust.call_args.args[:4], ('shop', 'fish', 'Wastage', 2.0))
        self.assertEqual(self.fish.adjust.call_args.kwargs, {'lot': 'expired'})
        self.doc.save.assert_called_once()

    def test_insufficient_replacement_does_not_save_or_post_wastage(self):
        self.fish.validate_order.side_effect = ValueError('Not enough unexpired stock')
        with patch.dict(sys.modules, {'local_commerce.services.orders': self.module}):
            with self.assertRaises(ValueError):
                self.recover('order-1')
        self.doc.save.assert_not_called()
        self.fish.adjust.assert_not_called()

    def test_dispatched_orders_are_not_changed(self):
        self.doc.status = 'Picked Up'
        with patch.dict(sys.modules, {'local_commerce.services.orders': self.module}):
            self.assertFalse(self.recover('order-1'))
        self.fish.validate_order.assert_not_called()
