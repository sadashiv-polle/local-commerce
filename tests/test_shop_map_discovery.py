import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


class TestShopMapDiscovery(unittest.TestCase):
    def setUp(self):
        import math

        tree = ast.parse((Path(__file__).resolve().parents[1] /
                         'local_commerce/services/shop_map_discovery.py').read_text())
        self.frappe = Mock()
        self.frappe.get_all.return_value = []
        self.ns = dict(math=math, frappe=self.frappe, SHOP_LISTING_FIELDS=['name', 'shop_name'],
                       serialize_public_shop=lambda row: row, map_config=lambda: {},
                       reject=lambda msg: (_ for _ in ()).throw(ValueError(msg)))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        module = ast.Module(body=functions, type_ignores=[])
        exec(compile(module, '<map discovery>', 'exec'), self.ns)

    def test_viewport_only_returns_active_shops_with_bounded_payload(self):
        self.ns['shops'](15, 73, 16, 74)
        args = self.frappe.get_all.call_args.kwargs
        self.assertEqual(args['filters'], [
            ['status', '=', 'Active'], ['latitude', '>=', 15], ['latitude', '<=', 16],
            ['longitude', '>=', 73], ['longitude', '<=', 74],
        ])
        self.assertEqual(args['limit_page_length'], 501)
        self.assertEqual(args['fields'], ['name', 'shop_name'])

    def test_invalid_areas_rejected_before_query(self):
        for bounds in [(16, 73, 15, 74), (15, 75, 16, 74), ('nan', 73, 16, 74),
                       (15, -181, 16, 74), (15, 73, 91, 74), (None, 73, 16, 74)]:
            with self.assertRaises(ValueError):
                self.ns['shops'](*bounds)
        self.frappe.get_all.assert_not_called()

    def test_missing_pins_excluded_and_large_areas_report_truncation(self):
        self.frappe.get_all.return_value = [{'name': 'missing', 'location': None}]
        self.assertEqual(self.ns['shops'](15, 73, 16, 74)['shops'], [])
        self.frappe.get_all.return_value = [{'name': str(i), 'location': {'latitude': 15.5}}
                                          for i in range(501)]
        result = self.ns['shops'](15, 73, 16, 74)
        self.assertTrue(result['has_more'])
        self.assertEqual(len(result['shops']), 500)
