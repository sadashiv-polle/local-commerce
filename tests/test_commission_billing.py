"""Exercise accounting decisions and signs without a running ERPNext site."""
import ast
import json
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from local_commerce.services.gst.commission_rules import signed_money
from local_commerce.services.gst.rules import amounts, split_tax
from local_commerce.services.payments.rules import money


class Row(dict):
    __getattr__ = dict.get


def load_function(path, name, scope):
    node = next(n for n in ast.parse(Path(path).read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
    node.body = [n for n in node.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
    exec(compile(ast.Module(body=[node],type_ignores=[]),path,'exec'),scope)
    return scope[name]


class CommissionBillingTests(unittest.TestCase):
    def setUp(self):
        self.records={}; self.journals=[];self.invoices=[]
        self.scope=dict(json=json,money=money,split_tax=split_tax,existing=self.records.get,
            reject=lambda message: (_ for _ in ()).throw(ValueError(message)))
        load_function('local_commerce/services/gst/accounting.py','line',self.scope)
        def journal(company,lines,remark,reverse=False):
            self.assertEqual(sum(Decimal(str(r.get('debit_in_account_currency',0))) for r in lines),
                             sum(Decimal(str(r.get('credit_in_account_currency',0))) for r in lines))
            self.journals.append((company,lines,reverse))
            return 'JE-'+str(len(self.journals))
        def record(order,snap,values,kind,pj,sj,refund_id='',original=None,**kwargs):
            row=Row(name='DOC-'+str(len(self.records)),payload=json.dumps({'amounts':values}),**kwargs)
            self.records[f'{order.name}:{kind}:{refund_id}']=row
            return row
        def invoice(order,snap,values,original=None):
            row=Row(name='INV-'+str(len(self.invoices)),original=original,values=values)
            self.invoices.append(row);return row
        self.scope.update(record=record,journal=journal,native_invoice=invoice,
            tax_heads=lambda order,snap,values,reverse=False:split_tax(values['commission_tax'],False))
        load_function('local_commerce/services/gst/commission.py','party_line',self.scope)
        self.post=load_function('local_commerce/services/gst/commission.py','post',self.scope)
        self.snap=dict(version=2,payment_method='Cashfree',shop_company='Vendor',shop_party={'state':'30','gstin':''},
            shop_payable='Vendor payable',expense='Vendor expense',shop_cost_center='Vendor CC',
            platform=dict(company='Platform',party={'state':'30'},cost_center='Platform CC',
                accounts={k:k for k in ('clearing','income','cgst','sgst','igst')}),
            billing=dict(receivable='Party receivable',deferred='Deferred',prepaid='Prepaid',customer='Vendor customer'))
        self.values=amounts(500,0,0,500,rate=10,inclusive=False,mode='Exempt goods')
        self.order=Row(name='order',status='Accepted',gateway_snapshot=json.dumps({'clearing_account':'Vendor gateway'}))

    def test_online_payment_defers_income_and_delivery_earns_once(self):
        self.post(self.order,self.snap,self.values)
        self.assertFalse(self.invoices)
        self.assertNotIn('income',[r['account'] for _,rows,_ in self.journals for r in rows])
        self.assertEqual(self.journals[0][1][0]['debit_in_account_currency'],59)
        self.post(self.order,self.snap,self.values)
        self.assertEqual(len(self.journals),2)
        self.order.status='Delivered'
        self.post(self.order,self.snap,self.values)
        self.post(self.order,self.snap,self.values)
        self.assertEqual(len(self.invoices),1)
        self.assertEqual(len(self.journals),4)
        self.assertEqual(self.journals[2][1][-1]['reference_name'],'INV-0')
        self.assertEqual(self.journals[3][1][-1]['account'],'Prepaid')

    def test_cod_only_earns_at_delivery_and_creates_receivable(self):
        self.snap['payment_method']='Cash on Delivery'
        self.post(self.order,self.snap,self.values)
        self.assertFalse(self.invoices)
        self.assertFalse(self.journals)
        self.order.status='Delivered'
        self.post(self.order,self.snap,self.values)
        self.assertEqual(len(self.invoices),1)
        self.assertEqual(len(self.journals),1) # only vendor journal; SI is platform revenue
        self.assertEqual(self.journals[0][1][-1]['account'],'Vendor payable')

    def test_pre_delivery_refund_reverses_advance_without_income(self):
        self.post(self.order,self.snap,self.values)
        self.post(self.order,self.snap,self.values,'refund')
        self.post(self.order,self.snap,self.values,'refund')
        self.assertFalse(self.invoices)
        self.assertEqual(len(self.journals),4)
        self.assertTrue(self.journals[-1][2])
        self.assertIn('order:Commission Advance Reversal:refund',self.records)

    def test_post_delivery_refund_creates_one_native_credit(self):
        self.post(self.order,self.snap,self.values)
        self.order.status='Delivered'
        self.post(self.order,self.snap,self.values)
        self.post(self.order,self.snap,self.values,'refund')
        self.post(self.order,self.snap,self.values,'refund')
        self.assertEqual(len(self.invoices),2)
        self.assertEqual(self.invoices[-1].original,'INV-0')
        self.assertEqual(self.journals[-2][1][0]['party'],'Vendor customer')
        self.assertTrue(self.journals[-1][2])

    def test_changed_retry_rejected(self):
        self.post(self.order,self.snap,self.values)
        with self.assertRaises(ValueError):
            self.post(self.order,self.snap,{**self.values,'commission_gross':'60.00'})

    def test_delivery_without_advance_rolls_back_in_transaction(self):
        self.order.status='Delivered'
        with self.assertRaises(ValueError):
            self.post(self.order,self.snap,self.values)

    def test_signed_balances_and_credit_amounts(self):
        self.assertEqual(signed_money('-59'),Decimal('-59.00'))
        self.assertEqual(sum(map(signed_money,['59','-20','-9'])),Decimal(30))
        for value in ('NaN','Infinity','bad'):
            with self.assertRaises(ValueError): signed_money(value)

    def test_three_credit_notes_reverse_exact_gst_heads(self):
        prior=[]
        scope=dict(json=json,money=money,split_tax=split_tax,
                   frappe=SimpleNamespace(get_all=lambda *a,**kw:prior))
        fn=load_function('local_commerce/services/gst/commission.py','tax_heads',scope)
        totals={k:Decimal(0) for k in ('cgst','sgst','igst')}
        for amount in ('0.35','0.35','0.37'):
            heads=fn(self.order,self.snap,{'commission_tax':amount},True)
            for k,v in heads.items():totals[k]+=Decimal(v)
            prior.append(json.dumps({'amounts':{'commission_tax':amount}}))
        self.assertEqual(totals, {k:Decimal(v) for k,v in split_tax('1.07',False).items()})

    def test_legacy_and_unconfigured_snapshots_are_not_version_two(self):
        fn=load_function('local_commerce/services/gst/commission.py','enabled',{})
        self.assertFalse(fn({'version':1}))
        self.assertFalse(fn({'version':2}))
        self.assertTrue(fn(self.snap))

    def test_report_denies_unscoped_non_admin(self):
        require_platform=Mock(side_effect=PermissionError)
        scope=dict(frappe=SimpleNamespace(utils=SimpleNamespace(getdate=lambda v:v)),require_platform=require_platform,
                   require_shop=Mock(),reject=Mock())
        fn=load_function('local_commerce/api/commissions.py','rows',scope)
        from datetime import date
        with self.assertRaises(PermissionError):fn(date(2026,1,1),date(2026,1,31))
        require_platform.assert_called_once()

    def test_report_denies_other_shop_before_reading_ledger(self):
        require_shop=Mock(side_effect=PermissionError)
        scope=dict(frappe=SimpleNamespace(utils=SimpleNamespace(getdate=lambda v:v)),require_platform=Mock(),
                   require_shop=require_shop,reject=Mock())
        fn=load_function('local_commerce/api/commissions.py','rows',scope)
        from datetime import date
        with self.assertRaises(PermissionError):fn(date(2026,1,1),date(2026,1,31),'other-shop')
        require_shop.assert_called_once_with('other-shop','write')

    def test_cancelled_and_failed_orders_do_not_earn(self):
        from contextlib import nullcontext
        for status,payment_status in [('Cancelled','Paid'),('Delivered','Failed')]:
            order=Row(name='order',status=status,payment_status=payment_status,payment_method='Cashfree',
                gst_snapshot=json.dumps(self.snap),sales_invoice='SI',payment_entry=None)
            post=Mock()
            scope=dict(json=json,enabled=lambda s:True,post=post,submitted=Mock(),posting=nullcontext,
                frappe=SimpleNamespace(get_doc=lambda *a,**kw:order),
                reject=lambda m:(_ for _ in ()).throw(ValueError(m)))
            fn=load_function('local_commerce/services/gst/commission.py','earn',scope)
            if status=='Cancelled': fn('order')
            else:
                with self.assertRaises(ValueError):fn('order')
            post.assert_not_called()

    def test_monthly_statement_and_reminder_retries_queue_once(self):
        from contextlib import nullcontext
        from datetime import date,timedelta
        from html import escape
        today=date(2026,6,1)  # Monday and first of month: two distinct messages.
        shop=Row(name='shop',shop_name='Shop',shop_email='billing@example.test',commission_customer='customer')
        send=Mock()
        def save(dt,name,field,value,**kwargs):shop[field]=value
        fake=SimpleNamespace(get_doc=lambda *a,**kw:shop,sendmail=send,
            db=SimpleNamespace(get_single_value=lambda *a:True,set_value=save),
            utils=SimpleNamespace(getdate=lambda v=None:v or today,add_days=lambda d,n:d+timedelta(days=n)))
        scope=dict(json=json,frappe=fake,escape=escape,posting=nullcontext,money=money,signed_money=signed_money,
            csv_bytes=lambda data:b'csv',rows=lambda *args:[dict(invoice='INV',outstanding='39',overdue=True)])
        queue=load_function('local_commerce/services/gst/commission_mail.py','queue',scope)
        queue('shop');queue('shop')
        self.assertEqual(send.call_count,2)
        self.assertEqual(len(json.loads(shop.commission_dispatch_json)),2)
        for call in send.call_args_list:
            self.assertTrue(call.kwargs['delayed'])
            self.assertEqual(call.kwargs['recipients'],['billing@example.test'])
