"""Accounting contracts for personally funded receipts, without a Frappe site."""
import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class StockFundingTests(TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.throw.side_effect = ValueError
        self.frappe.session.user = 'owner@example.com'
        tree = ast.parse(Path('local_commerce/services/stock_funding.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, (ast.Assign, ast.FunctionDef))]
        self.scope = dict(frappe=self.frappe, Decimal=Decimal)
        exec(compile(tree, 'stock_funding.py', 'exec'), self.scope)
        self.shop = SimpleNamespace(name='shop-a', company='Company A',
            stock_adjustment_account='Adjustment A', cost_center='Shop A')
        self.entry = SimpleNamespace(name='STE-1', total_incoming_value='74.70',
            posting_date='2026-10-25', docstatus=1, company='Company A')
        self.frappe.db.get_value.return_value = 'Owner funding A'
        self.frappe.get_doc.return_value.name = 'JV-1'

    def test_personal_funding_offsets_receipt_expense_credit_without_touching_stock(self):
        result = self.scope['post'](self.shop, self.entry, 'Personal funds')
        self.assertEqual(result, 'JV-1')
        journal = self.frappe.get_doc.call_args.args[0]
        debit, credit = journal['accounts']
        self.assertEqual(debit['account'], 'Adjustment A')
        self.assertEqual(credit['account'], 'Owner funding A')
        self.assertEqual(debit['debit_in_account_currency'], 74.70)
        self.assertEqual(credit['credit_in_account_currency'], 74.70)
        self.assertEqual(journal['company'], 'Company A')
        self.assertIn('STE-1', journal['user_remark'])
        self.frappe.get_doc.return_value.submit.assert_called_once()
        self.frappe.db.commit.assert_not_called()

    def test_nonperpetual_inventory_cannot_create_funding_journal(self):
        self.frappe.db.get_value.return_value = 0
        with self.assertRaises(ValueError):
            self.scope['post'](self.shop, self.entry, 'Personal funds')
        self.frappe.get_doc.assert_not_called()

    def test_adjustment_does_not_create_funding(self):
        self.assertIsNone(self.scope['post'](self.shop, self.entry, 'Stock adjustment'))
        self.frappe.get_doc.assert_not_called()

    def test_missing_or_foreign_funding_account_cannot_post(self):
        self.frappe.db.get_value.side_effect = [1, None]
        with self.assertRaises(ValueError):
            self.scope['post'](self.shop, self.entry, 'Personal funds')
        self.assertEqual(self.frappe.db.get_value.call_args.args[1]['company'], 'Company A')
        self.frappe.get_doc.assert_not_called()

    def test_wrong_company_draft_or_nonpositive_receipt_cannot_post(self):
        for field, value in [('company', 'Company B'), ('docstatus', 0), ('total_incoming_value', 0)]:
            original = getattr(self.entry, field)
            setattr(self.entry, field, value)
            with self.assertRaises(ValueError):
                self.scope['post'](self.shop, self.entry, 'Personal funds')
            setattr(self.entry, field, original)
        self.frappe.get_doc.assert_not_called()

    def test_invalid_funding_and_funding_of_removal_rejected(self):
        for action, source in [('Add', 'Arbitrary bank'), ('Remove', 'Personal funds')]:
            with self.assertRaises(ValueError): self.scope['validate_source'](action, source)

    def test_depreciation_cannot_be_used_for_fish_wastage(self):
        self.frappe.db.get_value.return_value = 'Depreciation'
        with self.assertRaises(ValueError): self.scope['validate_wastage']('Depreciation A')
        self.frappe.db.get_value.return_value = ''
        self.scope['validate_wastage']('Fish Wastage A')

    def test_linked_funding_journal_cannot_be_cancelled_alone(self):
        self.frappe.db.exists.return_value = True
        with self.assertRaises(ValueError): self.scope['protect_journal'](SimpleNamespace(name='JV-1'))
        self.frappe.db.exists.return_value = False
        self.scope['protect_journal'](SimpleNamespace(name='JV-2'))
