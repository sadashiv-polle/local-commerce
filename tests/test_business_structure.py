import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class BusinessStructureTests(TestCase):
    def setUp(self):
        source = ast.parse(Path('local_commerce/services/business_structure.py').read_text())
        source.body = [n for n in source.body if isinstance(n, ast.FunctionDef)]
        self.guard = Mock()
        self.db = SimpleNamespace(exists=Mock(return_value=False))
        def reject(message):
            raise ValueError(message)
        scope = dict(frappe=SimpleNamespace(throw=reject, db=self.db), require_platform=self.guard)
        exec(compile(source, '<structure>', 'exec'), scope)
        self.validate = scope['validate_shop_structure']

    def shop(self, **values):
        return SimpleNamespace(name='shop', get=values.get, get_doc_before_save=lambda:None)

    def test_owned_shop_without_self_commission(self):
        self.validate(self.shop(business_model='Owned shop', cashfree_commission=0))

    def test_owned_shop_rejects_marketplace_posting(self):
        for fields in (dict(gst_enabled=1), dict(cashfree_commission=7),
                       dict(cashfree_settlement_mode='Easy Split')):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.validate(self.shop(business_model='Owned shop', **fields))

    def test_legacy_documents_are_unchanged(self):
        self.validate(self.shop(cashfree_commission=7, gst_enabled=1))

    def test_vendor_cannot_use_retail_posting(self):
        with self.assertRaises(ValueError):
            self.validate(self.shop(business_model='Third-party vendor'))

    def test_changing_model_with_orders_requires_migration(self):
        doc = self.shop(business_model='Owned shop')
        doc.get_doc_before_save = lambda:self.shop(business_model='Legacy')
        self.db.exists.return_value = True
        with self.assertRaises(ValueError):
            self.validate(doc)
        self.guard.assert_called_once()
