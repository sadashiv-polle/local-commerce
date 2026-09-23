"""Verify delivery tabs filter before pagination and preserve access scope."""
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


class TestOrderDeliveryFilter(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] /
                         'local_commerce/services/orders.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'list_orders')
        self.frappe = Mock()
        self.frappe.session.user = 'customer'
        self.frappe.get_all.return_value = []
        self.scope = Mock()
        self.customer = Mock()
        ns = dict(frappe=self.frappe, require_shop=self.scope, customer_access=self.customer,
                  offset=int, serialize=lambda doc: doc,
                  reject=lambda msg: (_ for _ in ()).throw(ValueError(msg)))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<order list>', 'exec'), ns)
        self.list_orders = ns['list_orders']

    def test_each_tab_is_filtered_before_pagination(self):
        for mode in ['Normal', 'Scheduled']:
            self.list_orders(shop='own-shop', start=20, delivery_mode=mode)
            self.assertEqual(self.frappe.get_all.call_args.kwargs['filters'],
                             {'shop': 'own-shop', 'delivery_mode': mode})
            self.assertEqual(self.frappe.get_all.call_args.kwargs['start'], 20)
            self.assertEqual(self.frappe.get_all.call_args.kwargs['limit_page_length'], 20)
        self.scope.assert_called_with('own-shop')

    def test_customer_default_remains_all_own_orders(self):
        self.list_orders()
        self.assertEqual(self.frappe.get_all.call_args.kwargs['filters'],
                         {'customer_user': 'customer'})
        self.customer.assert_called_once()

    def test_invalid_mode_and_unauthorized_shop_are_rejected(self):
        with self.assertRaises(ValueError):
            self.list_orders(shop='shop', delivery_mode='anything')
        self.frappe.get_all.assert_not_called()
        self.scope.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.list_orders(shop='other-shop', delivery_mode='Scheduled')
        self.frappe.get_all.assert_not_called()


class TestRiderDeliveryFilter(unittest.TestCase):
    def test_modes_history_and_pagination_preserve_rider_scope(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] /
                         'local_commerce/services/orders.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'delivery_assignments')
        frappe = Mock()
        frappe.session.user = 'rider'
        frappe.get_all.return_value = []
        shops = Mock(return_value=['assigned-shop'])
        ns = dict(frappe=frappe, driver_shops=shops, offset=int, serialize=lambda doc: doc,
                  reject=lambda msg: (_ for _ in ()).throw(ValueError(msg)))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<delivery list>', 'exec'), ns)
        for mode in ['Normal', 'Scheduled']:
            for view in ['active', 'history']:
                ns['delivery_assignments'](20, view, mode)
                args = frappe.get_all.call_args.kwargs
                self.assertEqual(args['filters']['delivery_user'], 'rider')
                self.assertEqual(args['filters']['shop'], ['in', ['assigned-shop']])
                self.assertEqual(args['filters']['delivery_mode'], mode)
                self.assertEqual(args['start'], 20)
                self.assertEqual('Delivered' in args['filters']['status'][1], view == 'history')
        with self.assertRaises(ValueError):
            ns['delivery_assignments'](delivery_mode='invalid')
        shops.return_value = []
        frappe.get_all.reset_mock()
        self.assertEqual(ns['delivery_assignments'](delivery_mode='Normal'), [])
        frappe.get_all.assert_not_called()
