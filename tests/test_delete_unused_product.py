import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class TestDeleteUnusedProduct(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.LinkExistsError = type('LinkExistsError', (Exception,), {})
        self.frappe.db.exists.return_value = False
        self.frappe.get_all.return_value = []
        self.scope = Mock()
        self.owner = Mock()
        self.owner.own_item.return_value = (None, SimpleNamespace(name='item', modified='version'))
        self.owner.reject.side_effect = ValueError
        self.modules = patch.dict(sys.modules, {
            'frappe': self.frappe,
            'local_commerce.permissions.scope': self.scope,
            'local_commerce.services.owner': self.owner,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location(
            'delete_products_under_test',
            Path(__file__).resolve().parents[1] / 'local_commerce/services/products.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def delete(self, **kwargs):
        return self.module.delete_unused('shop', 'item', kwargs.get('modified', 'version'),
                                          kwargs.get('confirmation', 'item'))

    def test_unused_delete_keeps_native_link_checks_and_resets_scope(self):
        def native_delete(doctype, name, **kwargs):
            self.assertEqual(self.module._unused_item_deletion.get(), 'item')
            self.assertNotIn('force', kwargs)
            self.assertNotIn('ignore_links', kwargs)
            self.module.protect_item(SimpleNamespace(name='item'), 'on_trash')
        self.frappe.delete_doc.side_effect = native_delete
        self.assertTrue(self.delete()['deleted'])
        self.scope.require_platform.assert_called_once()
        self.owner.own_item.assert_called_once_with('shop', 'item', True)
        self.assertIsNone(self.module._unused_item_deletion.get())

    def test_owner_is_denied_before_reading_or_deleting(self):
        self.scope.require_platform.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.delete()
        self.owner.own_item.assert_not_called()
        self.frappe.delete_doc.assert_not_called()

    def test_wrong_confirmation_stale_record_and_history_block_delete(self):
        for args in [{'confirmation': 'other'}, {'modified': 'old'}]:
            with self.assertRaises(ValueError):
                self.delete(**args)
        for doctype in ['Sales Order Item', 'Stock Ledger Entry', 'LC Fish Lot']:
            self.frappe.db.exists.side_effect = lambda dt, filters: dt == doctype
            with self.assertRaises(ValueError):
                self.delete()
        self.frappe.delete_doc.assert_not_called()

    def test_stock_commitments_and_link_failures_block_delete(self):
        self.frappe.get_all.return_value = [{'actual_qty': 0, 'reserved_qty': 2}]
        with self.assertRaises(ValueError):
            self.delete()
        self.frappe.delete_doc.assert_not_called()
        self.frappe.get_all.return_value = []
        self.frappe.delete_doc.side_effect = self.frappe.LinkExistsError
        with self.assertRaises(ValueError):
            self.delete()
        self.frappe.db.rollback.assert_called_with(save_point='lc_delete_unused_product')
        self.assertIsNone(self.module._unused_item_deletion.get())
