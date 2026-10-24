"""Disposable-site native GL tests. Never run against a production site.

The platform fixture is a non-Indian INR Company so this tests ERPNext posting,
not India Compliance registration/classification. Validate Indian GST separately
on a configured staging Company before enabling native billing.
"""
import json
import frappe
from frappe.tests.utils import FrappeTestCase
from local_commerce.tests.test_payment_accounting import TestPaymentAccounting
from local_commerce.services.gst import commission
from local_commerce.services.gst.rules import amounts
from local_commerce.services.payments.accounting import posting
from local_commerce.api.commissions import receive


class TestCommissionBilling(FrappeTestCase):
    def setUp(self):
        TestPaymentAccounting.setUp(self)
        suffix=frappe.generate_hash(length=8)
        self.platform=frappe.get_doc(dict(doctype='Company',company_name='Commission Test '+suffix,
            abbr=suffix,country='United States',default_currency='INR')).insert()
        def account(company,root,label,kind=None):
            parent=frappe.db.get_value('Account',{'company':company,'root_type':root,'is_group':1},'name')
            return frappe.get_doc(dict(doctype='Account',company=company,account_name=label+' '+suffix,
                parent_account=parent,is_group=0,account_currency='INR',account_type=kind)).insert().name
        accounts={k:account(self.platform.name,root,k,kind) for k,root,kind in [
            ('clearing','Asset','Bank'),('bank','Asset','Bank'),('income','Income',None),
            ('cgst','Liability','Tax'),('sgst','Liability','Tax'),('igst','Liability','Tax')]}
        receivable=account(self.platform.name,'Asset','Commission debtor','Receivable')
        deferred=account(self.platform.name,'Liability','Commission deferred')
        prepaid=account(self.shop.company,'Asset','Commission prepaid')
        payable=account(self.shop.company,'Liability','Commission payable')
        customer=frappe.get_doc(dict(doctype='Customer',customer_name='Vendor billing '+suffix,
            customer_type='Company',customer_group='Commercial',territory='All Territories')).insert()
        service=frappe.get_doc(dict(doctype='Item',item_code='Commission '+suffix,item_name='Commission',
            item_group='Services',stock_uom='Nos',is_stock_item=0,is_sales_item=1)).insert()
        self.values=amounts(500,0,0,500,rate=10,inclusive=False,mode='Exempt goods')
        self.snap=dict(version=2,payment_method='Cashfree',amounts=self.values,mode='Exempt goods',
            commission_rate='10',registration='Unregistered',shop_company=self.shop.company,
            shop_party=dict(state='30',gstin='',legal_name='Test vendor',address='Test address'),
            shop_payable=payable,expense=self.expense,shop_cost_center=self.shop.cost_center,
            platform=dict(company=self.platform.name,party=dict(state='30',gstin=''),sac='998599',
                cost_center=self.platform.cost_center,accounts=accounts),
            billing=dict(customer=customer.name,receivable=receivable,deferred=deferred,prepaid=prepaid,
                item=service.name,uom='Nos',due_days=15))
        self.order.status='Accepted'
        self.order.delivered_at=frappe.utils.now_datetime()
        self.order.gst_snapshot=json.dumps(self.snap)

    def tearDown(self):
        frappe.set_user('Administrator')
        frappe.db.rollback()

    def test_cashfree_advance_invoice_refund_and_retries(self):
        with posting():
            commission.post(self.order,self.snap,self.values)
            commission.post(self.order,self.snap,self.values)
            self.order.status='Delivered'
            record=commission.post(self.order,self.snap,self.values)
            commission.post(self.order,self.snap,self.values)
            invoice=frappe.get_doc('Sales Invoice',record.sales_invoice)
            self.assertEqual(invoice.docstatus,1)
            self.assertAlmostEqual(invoice.grand_total,59)
            self.assertAlmostEqual(invoice.outstanding_amount,0)
            credit=commission.post(self.order,self.snap,self.values,'test-refund')
            commission.post(self.order,self.snap,self.values,'test-refund')
            note=frappe.get_doc('Sales Invoice',credit.sales_invoice)
            self.assertAlmostEqual(note.grand_total,-59)
            self.assertAlmostEqual(note.outstanding_amount,0)
            income=frappe.db.sql('''select sum(credit-debit) from `tabGL Entry`
                where company=%s and account=%s and is_cancelled=0''',
                (self.platform.name,self.snap['platform']['accounts']['income']))[0][0]
            self.assertAlmostEqual(float(income or 0),0)

    def test_cod_partial_receipt_retry_and_balance(self):
        self.snap['payment_method']='Cash on Delivery'
        self.order.status='Delivered'
        with posting():
            record=commission.post(self.order,self.snap,self.values)
        args=dict(document=record.name,amount=20,bank=self.snap['platform']['accounts']['bank'],
            shop_bank=self.bank.name,utr='commission-test-receipt',date=frappe.utils.nowdate())
        result=receive(**args)
        self.assertEqual(receive(**args),result)
        invoice=frappe.get_doc('Sales Invoice',record.sales_invoice)
        self.assertAlmostEqual(invoice.outstanding_amount,39)
        with self.assertRaises(frappe.ValidationError):
            receive(**{**args,'amount':21})
        with self.assertRaises(frappe.ValidationError):
            receive(**{**args,'amount':40,'utr':'another-reference'})
