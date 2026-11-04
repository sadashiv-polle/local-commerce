import ast
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from local_commerce.services.food_type import validate, catalog_filter


class FoodTypeTests(unittest.TestCase):
    def test_unknown_is_not_implicitly_vegetarian(self):
        self.assertEqual(validate(''), '')
        self.assertEqual(catalog_filter(''), {})
        self.assertEqual(catalog_filter('Veg'), {'lc_food_type': 'Veg'})
        self.assertEqual(catalog_filter('Non-veg'), {'lc_food_type': 'Non-veg'})
        for value in (None, [], {}, 'Chicken', 'veg', ['in', ['Veg']]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                catalog_filter(value)

    def test_create_persists_classification_and_rejects_retry_change(self):
        frappe = Mock()
        frappe.throw.side_effect = ValueError
        frappe.generate_hash.return_value = 'test-item'
        frappe.db.exists.return_value = True
        frappe.db.get_value.return_value = None
        shop = SimpleNamespace(name='shop', status='Active', company='company', warehouse='warehouse', cost_center='cost', get=lambda key: None)
        captured = {}
        def get_doc(value, *args):
            if value == 'LC Shop':
                return shop
            captured.update(value)
            return SimpleNamespace(insert=lambda **kwargs: None, get=value.get)
        frappe.get_doc.side_effect = get_doc
        with patch.dict(sys.modules, {'frappe': frappe, 'local_commerce.permissions.scope': Mock(), 'local_commerce.permissions.policy': Mock()}):
            spec = importlib.util.spec_from_file_location('food_products', Path('local_commerce/services/products.py'))
            service = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(service)
            result = service.create_item('shop', 'Eggs', 'Dairy & Eggs', 'Nos', lc_food_type='Non-veg')
            self.assertEqual(result['lc_food_type'], 'Non-veg')
            self.assertEqual(captured['lc_food_type'], 'Non-veg')
            existing = SimpleNamespace(item_name='Eggs', item_group='Dairy & Eggs', stock_uom='Nos', get=lambda key: 'Non-veg')
            frappe.db.get_value.return_value = existing
            with self.assertRaises(ValueError):
                service.create_item('shop', 'Eggs', 'Dairy & Eggs', 'Nos', request_key='request-key-123456', lc_food_type='Veg')
            self.assertIs(service.create_item('shop', 'Eggs', 'Dairy & Eggs', 'Nos', request_key='request-key-123456', lc_food_type='Non-veg'), existing)

    def test_catalog_filters_in_database_before_pagination(self):
        # Exercise the actual catalogue function up to its database page query.
        tree = ast.parse(Path('local_commerce/services/orders.py').read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'catalog')
        class PageQuery(Exception):
            pass
        for food_type in ('', 'Veg', 'Non-veg'):
            calls = []
            def get_all(doctype, **kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    return ['Fish', 'Vegetables']
                raise PageQuery
            env = dict(public_shop=lambda *a, **k: None, shop_location=lambda doc: None,
                       offset=int, frappe=SimpleNamespace(get_all=get_all))
            exec(compile(ast.Module(body=[function], type_ignores=[]), '<catalog>', 'exec'), env)
            with self.assertRaises(PageQuery):
                env['catalog']('shop', start=20, category='Fish', food_type=food_type)
            self.assertEqual(calls[1]['start'], 20)
            self.assertEqual(calls[1]['limit_page_length'], 21)
            self.assertEqual(calls[1]['filters'].get('lc_food_type', ''), food_type)
            self.assertEqual(calls[1]['filters']['lc_shop'], 'shop')
            self.assertEqual(calls[1]['filters']['item_group'], 'Fish')


if __name__ == '__main__':
    unittest.main()
