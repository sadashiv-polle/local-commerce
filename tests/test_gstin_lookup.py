import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

class LookupTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.guard = Mock()
        def reject(message): raise ValueError(message)
        self.scope = dict(frappe=self.frappe, require_platform=self.guard, reject=reject,
            gstin=Mock(side_effect=lambda number: number))
        tree = ast.parse(Path('local_commerce/services/gst/lookup.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        exec(compile(tree,'lookup.py','exec'),self.scope)
        self.number='30ABCDE1234F1Z5'

    def test_rejects_non_admin_before_provider_access(self):
        self.guard.side_effect=PermissionError
        with self.assertRaises(PermissionError): self.scope['lookup'](self.number)
        self.frappe.get_installed_apps.assert_not_called()

    def test_missing_optional_app_has_clear_error(self):
        self.frappe.get_installed_apps.return_value=['frappe','erpnext']
        with self.assertRaisesRegex(ValueError,'needs India Compliance'): self.scope['lookup'](self.number)

    def test_sandbox_not_fake_verified(self):
        self.frappe.get_installed_apps.return_value=['india_compliance']
        self.frappe.get_single.return_value={'sandbox_mode':1}
        with self.assertRaisesRegex(ValueError,'unavailable'): self.scope['lookup'](self.number)

    def test_mismatched_response_rejected(self):
        with self.assertRaises(ValueError): self.scope['normalize'](self.number,{'gstin':'OTHER'})

    def test_preserves_legal_name_separately_from_trade_name(self):
        value=self.scope['normalize'](self.number,dict(gstin=self.number,lgnm='Legal Owner',
            tradeNam='Shop brand',sts='Active',pradr={'addr':{'loc':'Market','city':'Panaji','pncd':'403001'}}))
        self.assertEqual(value['legal_name'],'Legal Owner')
        self.assertEqual(value['trade_name'],'Shop brand')
        self.assertEqual(value['city'],'Panaji')
        self.assertEqual(value['state'],'30')
        self.assertEqual(value['postal_code'],'403001')
        self.frappe.get_doc.assert_not_called()

    def test_cancelled_registration_is_not_reported_active(self):
        value=self.scope['normalize'](self.number,dict(gstin=self.number,sts='Cancelled'))
        self.assertEqual(value['status'],'Cancelled')
        self.assertEqual(value['address'],'')
