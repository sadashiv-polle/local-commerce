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

    def test_welcome_scheduled_only_after_successful_google_login_commits(self):
        self.frappe.local.request.path = '/api/method/frappe.integrations.oauth2_logins.login_via_google'
        self.scope['on_login'](SimpleNamespace(user='customer@example.com'))
        self.frappe.enqueue.assert_called_once_with(
            'local_commerce.services.social_login.queue_welcome', user='customer@example.com',
            queue='short', enqueue_after_commit=True)
        self.frappe.enqueue.reset_mock()
        self.frappe.local.request.path = '/api/method/login'
        self.scope['on_login'](SimpleNamespace(user='customer@example.com'))
        self.frappe.enqueue.assert_not_called()

    def welcome_account(self):
        account = Mock(enabled=1, user_type='Website User', first_name='<Customer>', email='customer@example.com')
        account.get.return_value = None
        account.get_social_login_userid.return_value = 'google-id'
        self.frappe.get_doc.return_value = account
        return account

    def run_welcome(self):
        from html import escape
        utils = SimpleNamespace(escape_html=escape, get_url=lambda p: 'https://example.com' + p,
                                now_datetime=lambda: '2026-10-25 20:00:00')
        with patch.dict(sys.modules, {'frappe.utils': utils}):
            self.scope['queue_welcome']('customer@example.com')

    def test_welcome_escapes_name_and_queues_without_saving_user(self):
        account = self.welcome_account()
        self.run_welcome()
        kwargs = self.frappe.sendmail.call_args.kwargs
        self.assertIn('&lt;Customer&gt;', kwargs['message'])
        self.assertFalse(kwargs['now'])
        self.assertEqual(kwargs['recipients'], ['customer@example.com'])
        self.frappe.db.set_value.assert_called_once()
        account.save.assert_not_called()
        self.frappe.db.commit.assert_not_called()

    def test_repeat_login_staff_disabled_and_non_google_are_skipped(self):
        for case in ('already_queued', 'staff', 'disabled', 'no_google'):
            account = self.welcome_account()
            if case == 'already_queued': account.get.return_value = '2026-10-25'
            if case == 'staff': account.user_type = 'System User'
            if case == 'disabled': account.enabled = 0
            if case == 'no_google': account.get_social_login_userid.return_value = None
            self.run_welcome()
        self.frappe.sendmail.assert_not_called()
        self.frappe.db.set_value.assert_not_called()

    def test_failed_email_queue_creation_does_not_mark_welcome_complete(self):
        self.welcome_account()
        self.frappe.sendmail.side_effect = RuntimeError('No outgoing email account')
        with self.assertRaises(RuntimeError): self.run_welcome()
        self.frappe.db.set_value.assert_not_called()
