"""Exercise report queries against relational fixtures, independently of a Bench."""

import importlib.util
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class Row(dict):
    def __getattr__(self, name):
        return self[name]


class TestFishReports(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            create table `tabItem` (name, item_name, stock_uom, lc_shop, current_price);
            create table `tabLC Order` (name, shop, delivery_note, sales_invoice);
            create table `tabSales Invoice` (name, lc_order, company, docstatus, posting_date);
            create table `tabSales Invoice Item`
                (parent, item_code, stock_qty, uom, qty, base_net_amount);
            create table `tabStock Ledger Entry`
                (item_code, actual_qty, stock_value_difference, voucher_type, voucher_no,
                 warehouse, company, is_cancelled, posting_date);
            create table `tabLC Fish Movement` (stock_entry, shop, kind);
            create table `tabSales Taxes and Charges`
                (parent, parenttype, charge_type, description, base_tax_amount);
            insert into `tabItem` values ('fish','Mackerel','Kg','shop-a',300),
                ('foreign','Other fish','Kg','shop-b',100);
            insert into `tabLC Order` values ('order','shop-a','DN','SI'),
                ('other','shop-b','DN-other','SI-other');
            insert into `tabSales Invoice` values ('SI','order','C',1,'2026-09-18'),
                ('draft','order','C',0,'2026-09-18'),
                ('SI-other','other','C',1,'2026-09-18');
            insert into `tabSales Invoice Item` values ('SI','fish',0.47,'Nos',7,245),
                ('SI','fish',1.02,'Kg',1.02,306), ('draft','fish',99,'Kg',99,9999),
                ('SI-other','foreign',10,'Kg',10,1000);
            insert into `tabStock Ledger Entry` values
                ('fish',8,800,'Stock Entry','old-receipt','W','C',0,'2026-09-17'),
                ('fish',2,240,'Stock Entry','receipt','W','C',0,'2026-09-18'),
                ('fish',-0.47,-47,'Delivery Note','DN','W','C',0,'2026-09-18'),
                ('fish',-1.02,-102,'Delivery Note','DN','W','C',0,'2026-09-18'),
                ('fish',-2,-200,'Stock Entry','waste','W','C',0,'2026-09-18'),
                ('fish',-0.5,-60,'Stock Entry','remove','W','C',0,'2026-09-18'),
                ('fish',100,999,'Stock Entry','cancelled','W','C',1,'2026-09-18'),
                ('foreign',10,1000,'Stock Entry','other-receipt','W','C',0,'2026-09-18');
            insert into `tabLC Fish Movement` values ('waste','shop-a','Wastage'),
                ('waste','shop-a','Wastage'), ('remove','shop-a','Remove');
            insert into `tabSales Taxes and Charges` values
                ('SI','Sales Invoice','Actual','Delivery charge',20),
                ('SI','Sales Invoice','On Net Total','VAT',99);
        ''')
        fake = Mock()
        fake.db.sql.side_effect = self.sql
        fake.db.get_value.return_value = 'INR'
        fake.get_doc.return_value = SimpleNamespace(company='C', warehouse='W')
        fake.get_all.side_effect = lambda *args, **kwargs: self.sql(
            "select name,item_name,stock_uom from `tabItem` "
            "where lc_shop=? and stock_uom in ('Kg','Nos')",
            (kwargs['filters']['lc_shop'],), as_dict=True)
        utilities = Mock(getdate=lambda value: date.fromisoformat(value))
        owner = Mock(reject=Mock(side_effect=ValueError))
        path = Path(__file__).resolve().parents[1] / 'local_commerce/services/fish_reports.py'
        spec = importlib.util.spec_from_file_location('lc_fish_report_under_test', path)
        self.module = importlib.util.module_from_spec(spec)
        self.scope = Mock()
        with patch.dict(sys.modules, {'frappe': fake, 'frappe.utils': utilities,
                                     'local_commerce.permissions.scope': self.scope,
                                     'local_commerce.services.fish': Mock(),
                                     'local_commerce.services.owner': owner}):
            spec.loader.exec_module(self.module)

    def tearDown(self):
        self.db.close()

    def sql(self, query, values=(), as_dict=False):
        parameters = tuple(value.isoformat() if isinstance(value, date) else value
                           for value in values)
        rows = self.db.execute(query.replace('%s', '?'), parameters).fetchall()
        return [Row(row) if as_dict else tuple(row) for row in rows]

    def test_actual_invoice_prices_and_delivery_cost_are_not_duplicated_by_options(self):
        report = self.module.report('shop-a', '2026-09-18', '2026-09-18')
        totals = report['totals']
        self.assertEqual(totals['revenue'], 551)
        self.assertEqual(totals['cost'], 149)
        self.assertEqual(totals['wastage_cost'], 200)
        self.assertEqual(totals['removal_cost'], 60)
        self.assertEqual(totals['profit_after_stock_losses'], 142)
        self.assertEqual(totals['delivery_revenue'], 20)
        self.assertEqual(totals['sold_pieces'], 7)
        self.assertAlmostEqual(totals['sold_kg'], 1.49)
        self.assertEqual(len(report['items']), 1)
        self.scope.require_shop.assert_called_once_with('shop-a', 'write')
        self.db.execute('update `tabItem` set current_price=9999')
        self.assertEqual(self.module.report(
            'shop-a', '2026-09-18', '2026-09-18')['totals']['revenue'], 551)

    def test_native_stock_dates_and_cancelled_entries_preserve_stock_equation(self):
        totals = self.module.report('shop-a', '2026-09-18', '2026-09-18')['totals']
        self.assertEqual(totals['opening_kg'], 8)
        self.assertEqual(totals['stock_in_kg'], 2)
        self.assertAlmostEqual(totals['stock_out_kg'], 3.99)
        self.assertAlmostEqual(totals['closing_kg'], 6.01)
        self.assertEqual(totals['closing_value'], 631)
        tomorrow = self.module.report('shop-a', '2026-09-19', '2026-09-19')['totals']
        self.assertEqual(tomorrow['revenue'], 0)
        self.assertEqual(tomorrow['wastage_cost'], 0)
        self.assertAlmostEqual(tomorrow['opening_kg'], 6.01)

    def test_invalid_date_range_is_rejected(self):
        for start, end in [('2026-09-19', '2026-09-18'),
                           ('2025-01-01', '2026-09-18'), ('invalid', '2026-09-18')]:
            with self.assertRaises(ValueError):
                self.module.report('shop-a', start, end)

    def test_piece_stock_and_money_combine_without_adding_pieces_to_kg(self):
        self.db.executescript("""
            insert into `tabItem` values ('pieces','Mackerel pieces','Nos','shop-a',12);
            insert into `tabLC Order` values ('pieces-order','shop-a','DN-pieces','SI-pieces');
            insert into `tabSales Invoice` values
                ('SI-pieces','pieces-order','C',1,'2026-09-18');
            insert into `tabSales Invoice Item` values ('SI-pieces','pieces',6,'Nos',6,72);
            insert into `tabStock Ledger Entry` values
                ('pieces',50,400,'Stock Entry','pieces-receipt','W','C',0,'2026-09-18'),
                ('pieces',-6,-48,'Delivery Note','DN-pieces','W','C',0,'2026-09-18'),
                ('pieces',-4,-32,'Stock Entry','pieces-waste','W','C',0,'2026-09-18');
            insert into `tabLC Fish Movement` values ('pieces-waste','shop-a','Wastage');
        """)
        report = self.module.report('shop-a', '2026-09-18', '2026-09-18')
        totals = report['totals']
        self.assertAlmostEqual(totals['sold_kg'], 1.49)
        self.assertEqual(totals['sold_pieces'], 13)
        self.assertEqual(totals['closing_pieces'], 40)
        self.assertEqual(totals['wastage_pieces'], 4)
        self.assertEqual(totals['revenue'], 623)
        self.assertEqual(totals['cost'], 197)
        self.assertEqual(totals['wastage_cost'], 232)
        row = next(row for row in report['items'] if row['item'] == 'pieces')
        self.assertEqual(row['sold_quantity'], 6)
        self.assertEqual(row['closing_quantity'], 40)
        self.assertEqual(row['stock_uom'], 'Nos')
        self.db.execute('update `tabItem` set current_price=100')
        self.assertEqual(self.module.report('shop-a', '2026-09-18', '2026-09-18')
                         ['totals']['revenue'], 623)
