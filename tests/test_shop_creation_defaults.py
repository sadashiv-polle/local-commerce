import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


class ShopCreationDefaults(TestCase):
    def test_settlement_mode_is_correct_at_first_insert_with_or_without_auto_setup(self):
        source = ast.parse(Path('local_commerce/services/admin.py').read_text())
        fn = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'create_shop')
        for model, company, expected in [('Owned shop', 'Platform', 'Direct merchant'),
                                         ('Third-party vendor', 'Vendor', 'Easy Split')]:
            for automatic in (0, 1):
                with self.subTest(model=model, auto_setup=automatic):
                    frappe = Mock()
                    frappe.db.exists.return_value = True
                    def document(values):
                        self.assertEqual(values['cashfree_settlement_mode'], expected)
                        doc = SimpleNamespace(**values, name='shop', insert=Mock())
                        return doc
                    frappe.get_doc.side_effect = document
                    scope = dict(frappe=frappe, require_platform=Mock(), reject=Mock(side_effect=ValueError))
                    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'admin.py', 'exec'), scope)
                    with patch.dict('sys.modules', {
                        'local_commerce.services.business_structure': SimpleNamespace(select_platform=lambda c: 'Platform'),
                        'local_commerce.services.shop_onboarding': SimpleNamespace(apply_details=Mock(), provision=Mock()),
                    }):
                        result = scope['create_shop']('Shop', company=company, business_model=model,
                                                     auto_setup=automatic)
                    self.assertEqual(result['company'], company)
                    self.assertEqual(result['accounts_configured'], bool(automatic))
