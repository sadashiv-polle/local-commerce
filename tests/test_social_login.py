import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


class SocialLoginTests(TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.throw.side_effect = ValueError
        self.frappe.db.exists.return_value = True
        self.frappe.db.get_single_value.return_value = 'LC Customer'
        tree = ast.parse(Path('local_commerce/services/social_login.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        self.scope = dict(frappe=self.frappe, re=re)
        exec(compile(tree, 'social_login.py', 'exec'), self.scope)

    def test_redirects_are_limited_to_local_app(self):
        for value in [None, '', 'https://evil.test', '//evil.test', '/admin', '/store#bad', '/store\\bad', '/store\n', '/store' + 'a'*1001]:
            self.assertEqual(self.scope['safe_destination'](value), '/local-commerce#/store')
        for value in ['/orders', '/shop/shop-id', '/store?search=fish', '/account']:
            self.assertEqual(self.scope['safe_destination'](value), '/local-commerce#' + value)

    def test_disabled_provider_does_not_start_oauth(self):
        self.frappe.db.exists.return_value = False
        with self.assertRaises(ValueError): self.scope['google_authorize']('/orders')

    def test_elevated_portal_default_is_rejected(self):
        for role in ['System Manager', 'LC Platform Administrator', 'LC Shop Owner', 'LC Delivery Person']:
            self.frappe.db.get_single_value.return_value = role
            with self.assertRaises(ValueError): self.scope['google_authorize']('/orders')

    def test_delegates_state_and_url_to_frappe_without_returning_keys(self):
        authorize = Mock(return_value='https://accounts.google.com/authorize?state=opaque')
        with patch.dict(sys.modules, {'frappe.utils.oauth': SimpleNamespace(get_oauth2_authorize_url=authorize)}):
            result = self.scope['google_authorize']('/orders')
        authorize.assert_called_once_with('google', '/local-commerce#/orders')
        self.assertEqual(set(result), {'url'})
        self.frappe.get_doc.assert_not_called()
