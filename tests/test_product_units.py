import ast
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock


class ProductUnitsTests(TestCase):
    def setUp(self):
        self.frappe = Mock()
        tree = ast.parse(Path('local_commerce/services/product_units.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, (ast.Assign, ast.FunctionDef))]
        self.scope = {'frappe': self.frappe}
        exec(compile(tree, 'product_units.py', 'exec'), self.scope)

    def test_fresh_install_creates_enabled_units_with_quantity_rules(self):
        self.frappe.db.exists.return_value = False
        self.scope['ensure_product_units']()
        rows = {c.args[0]['uom_name']: c.args[0] for c in self.frappe.get_doc.call_args_list}
        self.assertEqual(len(rows), 14)
        for name in ('Kg', 'Gram', 'Litre', 'Millilitre'):
            self.assertEqual(rows[name]['must_be_whole_number'], 0)
        for name in ('Plate', 'Pack', 'Bunch', 'Dozen'):
            self.assertEqual(rows[name]['must_be_whole_number'], 1)
        self.assertTrue(all(row['enabled'] == 1 for row in rows.values()))

    def test_repeat_migration_preserves_existing_units(self):
        self.frappe.db.exists.return_value = True
        self.scope['ensure_product_units']()
        self.frappe.get_doc.assert_not_called()
        self.frappe.db.set_value.assert_not_called()

    def test_upgrade_only_adds_missing_unit(self):
        self.frappe.db.exists.side_effect = lambda doctype, name: name != 'Plate'
        self.scope['ensure_product_units']()
        self.frappe.get_doc.assert_called_once_with(dict(doctype='UOM', uom_name='Plate', enabled=1, must_be_whole_number=1))
