import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class ShopGstCreationTests(TestCase):
    def setUp(self):
        self.doc = SimpleNamespace(name='shop', company='Company', insert=Mock())
        self.get_doc = Mock(return_value=self.doc)
        self.require_platform = Mock()
        scope = dict(frappe=SimpleNamespace(get_doc=self.get_doc), require_platform=self.require_platform,
                     reject=lambda msg: (_ for _ in ()).throw(ValueError(msg)))
        tree = ast.parse(Path('local_commerce/services/admin.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_shop')
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'admin', 'exec'), scope)
        self.create = scope['create_shop']

    def test_registered_shop_saves_normalized_gstin_without_enabling_tax(self):
        self.create('Shop', gst_registration='Registered', gst_number=' 27aapfu0939f1zv ')
        fields = self.get_doc.call_args.args[0]
        self.assertEqual(fields['gst_number'], '27AAPFU0939F1ZV')
        self.assertEqual(fields['gst_state'], '27')
        self.assertEqual(fields['gst_enabled'], 0)
        self.require_platform.assert_called_once()
        self.doc.insert.assert_called_once()

    def test_unregistered_shop_needs_no_gstin(self):
        self.create('Shop', gst_registration='Unregistered')
        fields = self.get_doc.call_args.args[0]
        self.assertEqual(fields['gst_registration'], 'Unregistered')
        self.assertEqual(fields['gst_number'], '')

    def test_old_clients_can_create_unconfirmed_drafts(self):
        self.create('Shop')
        self.assertEqual(self.get_doc.call_args.args[0]['gst_registration'], 'Unverified')

    def test_rejects_invalid_or_contradictory_registration_before_insert(self):
        for status, number in [('Registered',''),('Registered','27AAPFU0939F1ZA'),
                               ('Unregistered','27AAPFU0939F1ZV'),('other','')]:
            with self.assertRaises(ValueError):
                self.create('Shop', gst_registration=status, gst_number=number)
        self.get_doc.assert_not_called()

    def test_non_admin_cannot_create_shop(self):
        self.require_platform.side_effect = PermissionError()
        with self.assertRaises(PermissionError):
            self.create('Shop')
        self.get_doc.assert_not_called()
