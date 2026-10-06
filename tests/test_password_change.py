import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class PasswordChangeTests(unittest.TestCase):
    def test_requires_current_password_and_uses_authenticated_user(self):
        update = Mock()
        def reject(message):
            raise ValueError(message)
        frappe = SimpleNamespace(session=SimpleNamespace(user='person@example.com'), AuthenticationError=RuntimeError)
        tree = ast.parse(Path('local_commerce/api/session.py').read_text())
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'change_password']
        tree.body[0].decorator_list = []
        scope = {'frappe': frappe}
        exec(compile(tree, 'session.py', 'exec'), scope)
        with patch.dict('sys.modules', {'frappe.core.doctype.user.user': SimpleNamespace(update_password=update),
                                       'local_commerce.services.owner': SimpleNamespace(reject=reject)}):
            with self.assertRaises(ValueError):
                scope['change_password']('', 'new-password')
            update.assert_not_called()
            scope['change_password']('old-password', 'new-password')
            update.assert_called_once_with(new_password='new-password', old_password='old-password', logout_all_sessions=1)
            update.side_effect = RuntimeError('incorrect')
            with self.assertRaisesRegex(ValueError, 'Current password is incorrect'):
                scope['change_password']('wrong', 'new-password')
