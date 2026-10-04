import importlib.util
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        reject = Mock(side_effect=ValueError)
        with patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "local_commerce.services.owner": SimpleNamespace(reject=reject),
            },
        ):
            spec = importlib.util.spec_from_file_location(
                "reset_test", "local_commerce/services/password_reset.py"
            )
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

    def test_usernames_and_multiple_addresses_are_rejected(self):
        for email in ["aditya", "a@b.com,c@d.com", "Name <a@b.com>", None]:
            with self.assertRaises(ValueError):
                self.module.request(email)
        self.frappe.enqueue.assert_not_called()

    def test_request_is_generic_and_queues_normalized_email_after_commit(self):
        result = self.module.request(" A@Example.com ")
        self.assertEqual(result, {"message": self.module.MESSAGE})
        self.frappe.db.get_value.assert_not_called()
        self.assertEqual(self.frappe.enqueue.call_args.kwargs["email"], "a@example.com")
        self.assertTrue(self.frappe.enqueue.call_args.kwargs["enqueue_after_commit"])

    def test_unknown_and_builtin_accounts_do_not_send(self):
        for name in [None, "Guest", "Administrator"]:
            self.frappe.db.get_value.return_value = name
            self.module.send("a@example.com")
        self.frappe.get_doc.assert_not_called()

    def test_native_token_and_mail_use_registered_user(self):
        self.frappe.db.get_value.return_value = "a@example.com"
        user = self.frappe.get_doc.return_value
        user.email = "a@example.com"
        user.enabled = 1
        user._reset_password.return_value = "https://site/update-password?key=test"
        self.module.send("a@example.com")
        user.validate_reset_password.assert_called_once()
        user._reset_password.assert_called_once_with(send_email=False)
        self.assertFalse(user.send_login_mail.call_args.kwargs["now"])
        self.assertEqual(
            user.send_login_mail.call_args.args[2]["link"], "https://site/update-password?key=test"
        )

    def test_disabled_user_is_rechecked_in_worker(self):
        self.frappe.db.get_value.return_value = "a@example.com"
        user = self.frappe.get_doc.return_value
        user.enabled = 0
        self.module.send("a@example.com")
        user._reset_password.assert_not_called()
