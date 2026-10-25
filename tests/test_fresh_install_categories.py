"""An empty ERPNext site can install before the setup wizard creates its tree."""
import ast
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock


class FreshInstallCategories(TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.throw.side_effect = ValueError
        tree = ast.parse(Path('local_commerce/services/item_groups.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, (ast.Assign, ast.FunctionDef))]
        self.scope = {'frappe': self.frappe}
        exec(compile(tree, 'item_groups.py', 'exec'), self.scope)
        self.frappe.db.get_value.return_value = None
        self.frappe.db.exists.return_value = False
        self.frappe.db.get_single_value.return_value = 0

    def test_empty_pre_wizard_site_defers_without_creating_partial_categories(self):
        self.assertFalse(self.scope['ensure_item_groups']())
        self.frappe.get_doc.assert_not_called()

    def test_nonempty_broken_tree_is_not_hidden(self):
        self.frappe.db.exists.return_value = True
        with self.assertRaises(ValueError): self.scope['ensure_item_groups']()

    def test_completed_site_missing_tree_is_not_hidden(self):
        self.frappe.db.get_single_value.return_value = 1
        with self.assertRaises(ValueError): self.scope['ensure_item_groups']()

    def test_wizard_root_allows_seeding_then_repeat_preserves_categories(self):
        self.frappe.db.get_value.return_value = 'Actual Root'
        self.assertTrue(self.scope['ensure_item_groups']())
        self.assertEqual(self.frappe.get_doc.call_count, len(self.scope['COMMERCE_ITEM_GROUPS']))
        for call in self.frappe.get_doc.call_args_list:
            self.assertEqual(call.args[0]['parent_item_group'], 'Actual Root')
        self.frappe.get_doc.reset_mock()
        self.frappe.db.exists.return_value = True
        self.assertTrue(self.scope['ensure_item_groups']())
        self.frappe.get_doc.assert_not_called()

    def test_install_and_setup_hooks_only_seed_menu_when_groups_ready(self):
        tree = ast.parse(Path('local_commerce/install.py').read_text())
        for name in ('after_setup', 'after_migrate'):
            fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            guards = [n for n in ast.walk(fn) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == 'ensure_item_groups()']
            self.assertEqual(len(guards), 1)
            self.assertIn('seed_menu()', ast.unparse(guards[0]))
