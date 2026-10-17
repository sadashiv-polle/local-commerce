import ast
import json
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from local_commerce.services.gst.rules import amounts, gstin, refund_parts, split_tax
from local_commerce.services.gst.reports import csv_bytes, report_row
from local_commerce.services.payments.rules import money


class GstRulesTests(unittest.TestCase):
    def test_inclusive_restaurant_agreement(self):
        result = amounts(100, 0, 5, 105, mode='Restaurant 9(5)')
        for key, value in dict(commission_base='5.93', commission_tax='1.07', commission_gross='7.00',
                               eco_tax='5.00', vendor_amount='93.00').items():
            self.assertEqual(result[key], value)

    def test_delivery_not_commissioned_but_restaurant_taxed(self):
        result = amounts(100, 20, 6, 126, mode='Restaurant 9(5)')
        self.assertEqual(result['vendor_amount'], '113.00')
        self.assertEqual(result['commission_gross'], '7.00')

    def test_seller_tax_is_not_retained_by_platform(self):
        result = amounts(100, 0, 18, 118)
        self.assertEqual(result['vendor_amount'], '111.00')
        self.assertEqual(result['eco_tax'], '0.00')

    def test_exempt_fish_still_has_taxable_platform_service(self):
        result = amounts(100, 0, 0, 100, mode='Exempt goods')
        self.assertEqual(result['commission_tax'], '1.07')
        self.assertEqual(result['vendor_amount'], '93.00')

    def test_exclusive_commission(self):
        result = amounts(100, 0, 5, 105, inclusive=False, mode='Restaurant 9(5)')
        self.assertEqual(result['commission_gross'], '8.26')
        self.assertEqual(result['vendor_amount'], '91.74')

    def test_invalid_tax_and_totals_rejected(self):
        for args in [(100,0,5,100,'Seller GST'), (100,0,5,105,'Exempt goods'),
                     (100,0,18,118,'Restaurant 9(5)'), (100,0,0,100,'Legacy')]:
            with self.assertRaises(ValueError):
                amounts(*args[:4], mode=args[4])
        for value in ['NaN', '-1', 'Infinity', '100']:
            with self.assertRaises(ValueError):
                amounts(100,0,0,100,rate=value)

    def test_cumulative_partial_refunds_equal_full_invoice(self):
        original = amounts(100,0,5,105,mode='Restaurant 9(5)')
        previous = {}
        for base, tax in [(33,1.65),(66,3.30),(100,5)]:
            part = refund_parts(original,base,0,tax,previous)
            previous = {k:str(money(previous.get(k,0))+money(v)) for k,v in part.items()}
        self.assertEqual(previous, original)
        with self.assertRaises(ValueError):
            refund_parts(original,101,0,5,{})

    def test_delivery_only_refund_does_not_reverse_commission(self):
        original = amounts(100,20,6,126,mode='Restaurant 9(5)')
        part = refund_parts(original,0,20,1,{})
        self.assertEqual(part['commission_gross'], '0.00')
        self.assertEqual(part['vendor_amount'], '20.00')

    def test_tax_heads_preserve_every_paisa(self):
        for tax in ['0','1.07','5','10.33']:
            for interstate in (True,False):
                self.assertEqual(sum(map(Decimal,split_tax(tax,interstate).values())),Decimal(tax))

    def test_gstin_checksum(self):
        self.assertEqual(gstin('27AAPFU0939F1ZV'),'27AAPFU0939F1ZV')
        for value in ['','27AAPFU0939F1ZA','hello']:
            with self.assertRaises(ValueError):
                gstin(value)


class PostingTests(unittest.TestCase):
    def setUp(self):
        source=Path('local_commerce/services/gst/accounting.py').read_text()
        tree=ast.parse(source)
        self.records=[];self.journals=[]
        self.scope=dict(json=json,money=money,split_tax=split_tax,existing=lambda key:None,
                        reject=lambda message: (_ for _ in ()).throw(ValueError(message)))
        def journal(company,lines,remark,reverse=False):
            self.journals.append((company,lines,reverse));return 'JE-'+str(len(self.journals))
        self.scope.update(journal=journal,record=lambda *args:self.records.append(args))
        for name in ['line','post_documents']:
            node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'gst','exec'),self.scope)
        self.snap=dict(amounts=amounts(100,0,5,105,mode='Restaurant 9(5)'),mode='Restaurant 9(5)',
            shop_party={'state':'30'},shop_company='Shop',shop_payable='Payable to platform',
            shop_eco='ECO collected',expense='Commission expense',shop_cost_center='Shop CC',
            platform=dict(company='Platform',party={'state':'30'},cost_center='Platform CC',
                accounts={k:k for k in ['clearing','receivable','income','cgst','sgst','igst','eco_cgst','eco_sgst','eco_igst']}))
        self.order=SimpleNamespace(name='ORDER',gateway_snapshot=json.dumps({'clearing_account':'Shop clearing'}))

    def check(self,method):
        self.snap['payment_method']=method
        self.scope['post_documents'](self.order,self.snap,self.snap['amounts'])
        self.assertEqual(len(self.journals),4)
        for company, lines, reverse in self.journals:
            self.assertFalse(reverse)
            debit=sum(Decimal(str(r.get('debit_in_account_currency',0))) for r in lines)
            credit=sum(Decimal(str(r.get('credit_in_account_currency',0))) for r in lines)
            self.assertEqual(debit,credit)
        self.assertEqual(len(self.records),2)

    def test_cashfree_books_retained_funds_and_reduces_shop_clearing(self):
        self.check('Cashfree')
        self.assertEqual(self.journals[0][1][0]['account'],'clearing')
        self.assertEqual(self.journals[1][1][1]['account'],'Shop clearing')

    def test_cod_records_shop_debt_not_cashfree_cash(self):
        self.check('Cash on Delivery')
        self.assertEqual(self.journals[0][1][0]['account'],'receivable')
        self.assertEqual(self.journals[1][1][1]['account'],'Payable to platform')

    def test_existing_invoice_is_not_posted_again(self):
        self.snap['payment_method']='Cashfree'
        self.scope['existing']=lambda key:SimpleNamespace(payload=json.dumps({'amounts':self.snap['amounts']}))
        self.scope['post_documents'](self.order,self.snap,self.snap['amounts'])
        self.assertFalse(self.journals)

    def test_credit_reverses_both_companies(self):
        self.snap['payment_method']='Cashfree'
        self.scope['existing']=lambda key:SimpleNamespace(name='ORIGINAL') if key.endswith('Invoice:') else None
        self.scope['post_documents'](self.order,self.snap,self.snap['amounts'],'refund')
        self.assertTrue(all(row[2] for row in self.journals))
        self.assertEqual(len(self.records),2)


if __name__=='__main__':
    unittest.main()

class ActivationTests(unittest.TestCase):
    def test_missing_platform_gstin_blocks_activation_before_accounting(self):
        source=ast.parse(Path('local_commerce/services/gst/config.py').read_text())
        node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='profile')
        scope=dict(frappe=SimpleNamespace(get_single=lambda name:{}),identity=lambda settings:{'gstin':''},
            reject=lambda message: (_ for _ in ()).throw(ValueError(message)))
        exec(compile(ast.Module(body=[node],type_ignores=[]),'config','exec'),scope)
        with self.assertRaisesRegex(ValueError,'GSTIN'):
            scope['profile']()

    def test_csv_does_not_execute_formulas_or_change_credit_values(self):
        result=csv_bytes([dict(name='=SUM(1,2)', note='-cmd', amount='-7.00')]).decode('utf-8-sig')
        self.assertIn("'=SUM",result)
        self.assertIn("'-cmd",result)
        self.assertNotIn("'-7.00",result)
