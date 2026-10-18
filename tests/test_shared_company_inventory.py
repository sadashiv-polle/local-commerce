import ast
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


def load(name, **scope):
    tree = ast.parse(Path('local_commerce/services/owner.py').read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    exec(compile(tree, 'owner', 'exec'), scope)
    return scope[name]


class SharedCompanyInventoryTests(TestCase):
    def test_owner_cannot_rebind_inventory_to_other_shop(self):
        doc = SimpleNamespace(warehouse='Own', stock_adjustment_account='Own adjustment',cost_center='Own centre')
        guard = Mock(side_effect=PermissionError)
        configure = load('configure',shop_doc=Mock(return_value=doc))
        with patch.dict(sys.modules, {'local_commerce.permissions.scope':SimpleNamespace(require_platform=guard)}):
            with self.assertRaises(PermissionError):
                configure('shop','Other warehouse','Own adjustment','Own centre')
        self.assertEqual(doc.warehouse,'Own')
        guard.assert_called_once()

    def test_owner_options_do_not_enumerate_other_company_resources(self):
        doc=SimpleNamespace(company='Shared company',warehouse='Own',stock_adjustment_account='Adjustment',
                            cost_center='Centre',selling_price_list='Prices')
        frappe=SimpleNamespace(db=SimpleNamespace(get_value=Mock(return_value='INR')),get_all=Mock())
        options=load('setup_options',shop_doc=Mock(return_value=doc),tenant_user=lambda:('owner',[],True),frappe=frappe)
        result=options('shop')
        self.assertEqual(result['warehouses'],['Own'])
        self.assertEqual(result['accounts'],['Adjustment'])
        self.assertEqual(result['cost_centers'],['Centre'])
        frappe.get_all.assert_not_called()
