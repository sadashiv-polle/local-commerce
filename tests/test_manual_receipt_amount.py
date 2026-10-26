"""Exercise the receipt row against ERPNext 15.109's manual-rate behavior."""
import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase


class ManualReceiptAmountTests(TestCase):
    def receipt_row(self, quantity, cost):
        tree = ast.parse(Path('local_commerce/services/owner.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'adjust_stock')
        # Execute the production Add/Remove row setup, avoiding the Frappe runtime.
        branch = next(n for n in fn.body if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "action == 'Add'")
        module = ast.Module(body=[branch], type_ignores=[])
        scope = dict(action='Add', row={}, qty=Decimal(quantity), cost=Decimal(cost),
                     doc=SimpleNamespace(warehouse='Shop warehouse'))
        exec(compile(module, 'receipt_row', 'exec'), scope)
        return scope['row']

    def test_old_erpnext_manual_rate_path_keeps_positive_value(self):
        row = self.receipt_row('6', '12.45')
        # In 15.109 set_basic_rate skips this row; update_valuation_rate uses basic_amount.
        incoming_value = round(float(row.get('basic_amount') or 0), 2)
        self.assertEqual(incoming_value, 74.70)
        self.assertEqual(row['basic_rate'], 12.45)
        self.assertEqual(row['set_basic_rate_manually'], 1)

    def test_fractional_stock_cost_and_pack_quantity(self):
        self.assertEqual(self.receipt_row('0.75', '240')['basic_amount'], 180)
        self.assertEqual(self.receipt_row('10', '80')['basic_amount'], 800)
