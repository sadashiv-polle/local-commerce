import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from local_commerce.services.return_rules import approved_amount, refund_evidence, refund_payload


class ReturnMoneyTests(unittest.TestCase):
    def setUp(self):
        self.snap = dict(order_id='order1', amount='370.00', currency='INR',
            settlement_mode='Easy Split', vendor_id='vendor1', vendor_amount='343.00')
        self.case = dict(refund_id='return1', amount='370.00')
        self.row = dict(refund_id='return1', cf_refund_id='cf1', cf_payment_id='pay1',
            order_id='order1', refund_currency='INR', refund_amount=370, refund_status='SUCCESS')

    def test_full_uses_paid_total_including_charges(self):
        self.assertEqual(str(approved_amount('Full', None, 370, 0)), '370.00')
        self.assertEqual(str(approved_amount('Full', None, 370, 20)), '350.00')

    def test_invalid_partial_amounts(self):
        for value in (0, -1, 371, 'NaN', 'Infinity', 'junk'):
            with self.assertRaises(ValueError): approved_amount('Partial', value, 370, 0)

    def test_previous_refund_reduces_balance(self):
        with self.assertRaises(ValueError): approved_amount('Partial', 360, 370, 20)

    def test_matching_refund_is_recovered_after_timeout(self):
        result = refund_evidence([self.row], self.snap, 'pay1', 'return1', 370)
        self.assertEqual(result, self.row)

    def test_pending_external_refund_reserves_balance(self):
        self.row.update(refund_id='other', refund_amount=20, refund_status='PENDING')
        with self.assertRaises(ValueError): refund_evidence([self.row],self.snap,'pay1','return1',370)

    def test_wrong_identity_or_changed_amount_rejected(self):
        for field, value in [('order_id','other'),('cf_payment_id','other'),('refund_currency','USD'),('refund_amount',369)]:
            with self.assertRaises(ValueError):
                refund_evidence([{**self.row,field:value}], self.snap,'pay1','return1',370)

    def test_failed_id_is_not_replaced_with_new_refund(self):
        self.row['refund_status']='FAILED'
        self.assertEqual(refund_evidence([self.row],self.snap,'pay1','return1',370)['refund_status'],'FAILED')

    def test_duplicate_history_rejected(self):
        with self.assertRaises(ValueError): refund_evidence([self.row,self.row],self.snap,'pay1','return1',370)

    def test_full_split_reverses_original_vendor_share(self):
        payload = refund_payload(self.case,self.snap)
        self.assertEqual(payload['refund_amount'],370)
        self.assertEqual(payload['refund_splits'],[dict(vendor_id='vendor1',amount=343)])

    def test_partial_split_rounding_and_direct_merchant(self):
        self.case['amount']='100'
        self.assertEqual(refund_payload(self.case,self.snap)['refund_splits'][0]['amount'],92.70)
        self.snap['settlement_mode']='Direct merchant'
        self.assertNotIn('refund_splits',refund_payload(self.case,self.snap))


class ReturnPermissionTests(unittest.TestCase):
    def setUp(self):
        def reject(message): raise ValueError(message)
        self.frappe=Mock(session=SimpleNamespace(user='customer'), PermissionError=PermissionError)
        self.frappe.throw.side_effect=PermissionError
        self.guard=Mock()
        self.scope=dict(frappe=self.frappe,require_platform=self.guard,require_shop=Mock(),reject=reject,
            json=json,cashfree=Mock())
        tree=ast.parse(Path('local_commerce/services/returns.py').read_text())
        tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        exec(compile(tree,'returns.py','exec'),self.scope)

    def test_customer_cannot_approve_or_retry_refund(self):
        self.guard.side_effect=PermissionError
        with self.assertRaises(PermissionError): self.scope['decide']('order','Approve','reason')
        with self.assertRaises(PermissionError): self.scope['retry']('order')
        self.frappe.get_doc.assert_not_called()

    def test_other_customer_cannot_request_return(self):
        self.frappe.get_doc.return_value=SimpleNamespace(customer_user='someone_else')
        with self.assertRaises(PermissionError): self.scope['request_return']('order','reason')
        self.frappe.db.sql.assert_not_called()

    def test_only_delivered_orders_allow_return_request(self):
        doc=SimpleNamespace(customer_user='customer',status='Ready')
        self.frappe.get_doc.return_value=doc
        self.scope['lock']=Mock(return_value=doc)
        with self.assertRaisesRegex(ValueError,'after delivery'): self.scope['request_return']('order','reason')

    def test_shop_review_requires_shop_scope(self):
        self.frappe.get_doc.return_value=SimpleNamespace(shop='other_shop')
        self.scope['require_shop'].side_effect=PermissionError
        with self.assertRaises(PermissionError):self.scope['review']('order','review')
        self.scope['require_shop'].assert_called_once_with('other_shop','write')
        self.frappe.db.sql.assert_not_called()

    def test_repeated_request_returns_existing_case(self):
        doc=SimpleNamespace(customer_user='customer',status='Delivered')
        self.frappe.get_doc.return_value=doc
        self.scope['lock']=Mock(return_value=doc)
        self.scope['state']=Mock(return_value={'status':'Requested'})
        self.scope['public']=Mock(return_value={'status':'Requested'})
        self.assertEqual(self.scope['request_return']('order','reason'),{'status':'Requested'})
        self.scope['cashfree'].save.assert_not_called()

    def test_failed_mutex_does_not_change_another_workers_case(self):
        self.scope['cashfree'].begin_operation.side_effect=ValueError('busy')
        self.scope['lock']=Mock()
        self.scope['process']('order')
        self.scope['lock'].assert_not_called()

    def test_public_summary_does_not_expose_provider_payload_or_user_emails(self):
        self.scope['state']=Mock(return_value={'status':'Requested','reason':'damaged',
            'payload':{'vendor_id':'private'},'approved_by':'admin@example.com','refund_id':'secret'})
        self.assertEqual(self.scope['public'](None),{'status':'Requested','reason':'damaged'})

class ReturnWorkerTests(unittest.TestCase):
    def setUp(self):
        self.frappe=Mock()
        self.gateway=Mock()
        self.case=dict(status='Refund queued',amount='100.00',refund_id='ret_fixed',
            payload=dict(refund_id='ret_fixed',refund_amount=100,refund_note='Local dot return ret_fixed',refund_speed='STANDARD'))
        self.doc=SimpleNamespace(name='order',gateway_profile='profile',gateway_order_id='remote',
            gateway_payment_id='payment',gateway_snapshot=json.dumps(dict(amount='100',currency='INR',settlement_mode='Direct merchant')))
        self.gateway.payment_order.return_value=self.doc
        self.gateway.locked.return_value=self.doc
        self.scope=dict(frappe=self.frappe,cashfree=self.gateway,json=json,
            quote=lambda s,**k:s,refund_evidence=refund_evidence)
        tree=ast.parse(Path('local_commerce/services/returns.py').read_text())
        tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        exec(compile(tree,'returns.py','exec'),self.scope)
        self.scope['state']=lambda doc:self.case
        self.scope['lock']=Mock(return_value=self.doc)
        self.scope['save']=Mock(side_effect=lambda doc,case,status:case.update(status=status))
        self.row=dict(refund_id='ret_fixed',cf_refund_id='provider',cf_payment_id='payment',order_id='remote',
            refund_currency='INR',refund_amount=100,refund_status='PENDING')

    def test_creation_uses_persisted_id_payload_and_key(self):
        self.gateway.request.side_effect=[[],{},[self.row]]
        self.scope['process']('order')
        post=self.gateway.request.call_args_list[1]
        self.assertEqual(post.args,('profile','POST','/orders/remote/refunds',self.case['payload']))
        self.assertEqual(post.kwargs,dict(key='remote:ret_fixed'))
        self.assertEqual(self.case['status'],'Refund processing')
        self.gateway.sync.assert_called_once_with('order',authorize=False)

    def test_retry_of_existing_refund_does_not_post_again(self):
        self.gateway.request.return_value=[self.row]
        self.scope['process']('order')
        self.assertEqual(self.gateway.request.call_count,1)
        self.assertEqual(self.gateway.request.call_args.args[1],'GET')

    def test_timeout_keeps_same_id_for_administrator_retry(self):
        self.gateway.request.side_effect=[[],TimeoutError()]
        self.scope['process']('order')
        self.assertEqual(self.case['status'],'Needs review')
        self.assertEqual(self.case['refund_id'],'ret_fixed')
        self.gateway.sync.assert_not_called()

    def test_external_pending_refund_blocks_new_transfer(self):
        self.gateway.request.return_value=[{**self.row,'refund_id':'external','refund_amount':10}]
        self.scope['process']('order')
        self.assertEqual(self.case['status'],'Needs review')
        self.assertEqual(self.gateway.request.call_count,1)

class ManualReturnTests(unittest.TestCase):
    def test_manual_refund_checks_admin_before_reading_documents(self):
        tree=ast.parse(Path('local_commerce/services/returns.py').read_text())
        tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        guard=Mock(side_effect=PermissionError)
        frappe=Mock()
        scope=dict(frappe=frappe,require_platform=guard)
        exec(compile(tree,'returns.py','exec'),scope)
        with self.assertRaises(PermissionError):scope['record_manual']('order','credit','payment','reason')
        frappe.get_doc.assert_not_called()

    def test_manual_refund_requires_matching_submitted_documents(self):
        from local_commerce.services.payments.rules import money
        class Doc(SimpleNamespace):
            def get(self,key):return getattr(self,key,None)
        tree=ast.parse(Path('local_commerce/services/returns.py').read_text())
        tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        def reject(message):raise ValueError(message)
        frappe=Mock(session=SimpleNamespace(user='Administrator'))
        scope=dict(frappe=frappe,require_platform=Mock(),money=money,reject=reject)
        exec(compile(tree,'returns.py','exec'),scope)
        scope['lock']=Mock(return_value=Doc(payment_method='Cash on Delivery',sales_invoice='invoice'))
        scope['state']=Mock(return_value=dict(status='Reviewed'))
        scope['save']=Mock()
        scope['public']=Mock()
        invoice=Doc(name='invoice',docstatus=1,company='Shop',customer='customer',currency='INR',grand_total=100)
        credit=Doc(name='credit',docstatus=1,is_return=1,return_against='invoice',company='Shop',customer='customer',
            currency='INR',grand_total=-100,outstanding_amount=0,update_stock=0)
        payment=Doc(name='payment',docstatus=1,payment_type='Pay',company='Shop',party_type='Customer',party='customer',
            paid_from_account_currency='INR',paid_to_account_currency='INR',paid_amount=100,
            references=[Doc(reference_doctype='Sales Invoice',reference_name='credit',allocated_amount=-100)])
        for bad_field,bad_value in [('docstatus',0),('party','other'),('paid_amount',99)]:
            original=getattr(payment,bad_field);setattr(payment,bad_field,bad_value)
            frappe.get_doc.side_effect=[invoice,credit,payment]
            with self.assertRaises(ValueError):scope['record_manual']('order','credit','payment','paid manually')
            setattr(payment,bad_field,original)
        scope['save'].assert_not_called()
        frappe.get_doc.side_effect=[invoice,credit,payment]
        scope['record_manual']('order','credit','payment','paid manually')
        self.assertEqual(scope['save'].call_args.args[2],'Manual refund recorded')
