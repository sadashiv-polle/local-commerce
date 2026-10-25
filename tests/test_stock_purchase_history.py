"""Shop-wide stock history must remain tenant scoped and preserve stored costs."""
import ast
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock


class PurchaseHistoryTests(TestCase):
    def setUp(self):
        tree = ast.parse(Path('local_commerce/services/owner.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'history']
        self.frappe = Mock()
        self.guard = Mock()
        self.own_item = Mock()
        self.scope = dict(frappe=self.frappe, require_shop=self.guard, own_item=self.own_item,
                          reject=Mock(side_effect=ValueError))
        exec(compile(tree, 'owner.py', 'exec'), self.scope)

    def test_purchase_list_is_scoped_and_excludes_adjustments(self):
        self.scope['history']('shop-a', purchases_only='1')
        self.guard.assert_called_once_with('shop-a', 'read')
        args = self.frappe.get_all.call_args.kwargs
        self.assertEqual(args['filters'], dict(shop='shop-a', action='Add', stock_source=['in', ['Personal funds', 'Shop cash or bank', 'Supplier credit']]))
        self.assertIn('unit_cost', args['fields'])
        self.assertIn('currency', args['fields'])
        self.assertEqual(args['limit_page_length'], 20)

    def test_unauthorized_shop_is_not_queried(self):
        self.guard.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.scope['history']('other-shop')
        self.frappe.get_all.assert_not_called()

    def test_product_history_still_checks_ownership(self):
        self.scope['history']('shop-a', 'item-a', 20)
        self.own_item.assert_called_once_with('shop-a', 'item-a')
        self.assertEqual(self.frappe.get_all.call_args.kwargs['filters'], dict(shop='shop-a', item='item-a'))

    def test_negative_page_is_rejected(self):
        with self.assertRaises(ValueError):
            self.scope['history']('shop-a', start=-20)
        self.frappe.get_all.assert_not_called()
