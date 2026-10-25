import ast
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class WorkspaceErrorsTests(TestCase):
    def setUp(self):
        tree = ast.parse(Path('local_commerce/api/workspace_errors.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        self.response = {}
        self.guard = Mock()
        scope = dict(wraps=wraps, require_shop=self.guard,
                     strip_html=lambda s: s.replace('<b>', '').replace('</b>', ''),
                     frappe=SimpleNamespace(ValidationError=ValueError,
                         local=SimpleNamespace(response=self.response)))
        exec(compile(tree, 'workspace_errors.py', 'exec'), scope)
        self.decorate = scope['workspace_validation']

    def test_validation_is_readable_and_still_raises(self):
        failure = ValueError('<b>Set default payable account</b>')
        fn = Mock(side_effect=failure)
        with self.assertRaises(ValueError) as caught:
            self.decorate(fn)('shop-a')
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.response['lc_message'], 'Shop workspace: Set default payable account')

    def test_denied_access_does_not_call_function_or_expose_detail(self):
        self.guard.side_effect = PermissionError
        fn = Mock()
        with self.assertRaises(PermissionError):
            self.decorate(fn)('shop-b')
        fn.assert_not_called()
        self.assertEqual(self.response, {})

    def test_unexpected_exception_is_not_exposed(self):
        with self.assertRaises(RuntimeError):
            self.decorate(Mock(side_effect=RuntimeError('private traceback')))('shop-a')
        self.assertEqual(self.response, {})

    def test_existing_safe_message_is_preserved(self):
        self.response['lc_message'] = 'Existing guidance'
        with self.assertRaises(ValueError):
            self.decorate(Mock(side_effect=ValueError('details')))('shop-a')
        self.assertEqual(self.response['lc_message'], 'Existing guidance')
