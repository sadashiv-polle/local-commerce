import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


class AdminCreationErrors(TestCase):
    def setUp(self):
        self.frappe = Mock(ValidationError=ValueError)
        self.frappe.local.response = {}
        self.admin = Mock()
        self.guard = Mock()
        tree = ast.parse(Path('local_commerce/api/admin.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_shop')
        fn.decorator_list = []
        self.scope = dict(frappe=self.frappe, admin=self.admin)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'admin.py', 'exec'), self.scope)

    def call(self):
        with patch.dict('sys.modules', {
            'local_commerce.permissions.scope': SimpleNamespace(require_platform=self.guard),
            'frappe.utils': SimpleNamespace(strip_html=lambda value: value.replace('<b>', '').replace('</b>', '')),
        }):
            return self.scope['create_shop']('Shop')

    def test_native_validation_is_visible_and_still_raises_for_rollback(self):
        self.admin.create_shop.side_effect = ValueError('Missing <b>Company cost center</b>')
        with self.assertRaises(ValueError): self.call()
        self.assertEqual(self.frappe.local.response['lc_message'], 'Shop setup: Missing Company cost center')

    def test_existing_public_message_is_preserved(self):
        self.frappe.local.response['lc_message'] = 'Select an INR account'
        self.admin.create_shop.side_effect = ValueError('internal')
        with self.assertRaises(ValueError): self.call()
        self.assertEqual(self.frappe.local.response['lc_message'], 'Select an INR account')

    def test_access_denied_does_not_call_service(self):
        self.guard.side_effect = PermissionError
        with self.assertRaises(PermissionError): self.call()
        self.admin.create_shop.assert_not_called()

    def test_unexpected_exceptions_are_not_exposed(self):
        self.admin.create_shop.side_effect = RuntimeError('private server details')
        with self.assertRaises(RuntimeError): self.call()
        self.assertEqual(self.frappe.local.response, {})
