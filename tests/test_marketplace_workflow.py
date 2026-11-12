"""Exercise workflow functions with database/provider doubles; no live transfers."""
import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from local_commerce.services import cancellation_policy as policy


class Doc(SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)


def functions(*names, **scope):
    tree = ast.parse(Path('local_commerce/services/marketplace.py').read_text())
    class Imports(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            return None
    body = [Imports().visit(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    scope.update(json=json, policy=policy)
    exec(compile(ast.Module(body=body, type_ignores=[]), 'marketplace.py', 'exec'), scope)
    return scope


def reject(msg):
    raise ValueError(msg)


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.doc = Doc(name='order', status='Preparing')
        self.case = {'status':'Awaiting approvals'}
        self.frappe = Mock(); self.frappe.session.user = 'owner'
        self.frappe.get_doc.return_value = self.doc
        self.cashfree = Mock(); self.cashfree.locked.return_value = self.doc
        self.cancel = Mock(); self.event = Mock()
        self.scope = functions('approve', frappe=self.frappe, cashfree=self.cashfree,
            require_platform=Mock(), owner=lambda doc: self.frappe.session.user == 'owner',
            returns=SimpleNamespace(note=lambda value: value), orders=Mock(), reject=reject,
            state=lambda doc:self.case, save=lambda doc,case,status:case.update(status=status),
            event=self.event, cancel=self.cancel)

    def decide(self, role, decision='Approve'):
        return self.scope['approve']('order',decision,'valid reason',role)

    def test_two_distinct_approvals_required(self):
        self.decide('Shop')
        self.cancel.assert_not_called()
        self.assertEqual(self.case['status'], 'Awaiting approvals')
        self.frappe.session.user = 'admin'
        self.decide('Admin')
        self.cancel.assert_called_once()
        self.assertEqual(self.case['status'], 'Approved')

    def test_admin_first_also_requires_owner(self):
        self.frappe.session.user = 'admin'; self.decide('Admin')
        self.cancel.assert_not_called()
        self.frappe.session.user = 'owner'; self.decide('Shop')
        self.cancel.assert_called_once()

    def test_same_person_cannot_approve_both_roles(self):
        self.decide('Shop')
        with self.assertRaisesRegex(ValueError,'different people'):
            self.decide('Admin')
        self.cancel.assert_not_called()

    def test_rejection_does_not_cancel(self):
        self.decide('Shop','Reject')
        self.assertEqual(self.case['status'], 'Rejected')
        self.cancel.assert_not_called()
        with self.assertRaisesRegex(ValueError,'no longer'):
            self.decide('Admin')

    def test_repeated_approval_does_not_repeat_event(self):
        self.decide('Shop'); self.decide('Shop')
        self.event.assert_called_once()
        self.cancel.assert_not_called()

    def test_admin_permission_checked(self):
        self.scope['require_platform'].side_effect = PermissionError
        with self.assertRaises(PermissionError): self.decide('Admin')
        self.cashfree.begin_operation.assert_not_called()


class ProviderIntentTests(unittest.TestCase):
    def setUp(self):
        self.doc = Doc(name='o', gateway_profile='g')
        self.op = Doc(name='op', kind='Delivery split', status='Queued', operation_key='o:split', payload_json=json.dumps({'split':[{'amount':93}]}))
        self.frappe = Mock(); self.frappe.get_doc.return_value=self.op
        self.cashfree = Mock(); self.cashfree.locked.return_value=self.doc
        self.cashfree.request.return_value={'status':'OK'}
        self.scope=functions('send',frappe=self.frappe,cashfree=self.cashfree,reject=reject,
            op_save=lambda op,status,response=None:setattr(op,'status',status),event=Mock())

    def test_intent_is_committed_before_post(self):
        def request(*args,**kwargs):
            self.assertEqual(self.op.status,'Unconfirmed')
            self.frappe.db.commit.assert_called_once()
            self.assertEqual(kwargs['key'],'o:split')
            return {'status':'OK'}
        self.cashfree.request.side_effect=request
        self.scope['send'](self.doc,self.op,'/split')
        self.assertEqual(self.op.status,'Accepted')

    def test_accepted_operation_is_not_resent(self):
        self.op.status='Accepted'
        self.scope['send'](self.doc,self.op,'/split')
        self.cashfree.request.assert_not_called()

    def test_timeout_does_not_allow_duplicate_transfer(self):
        self.cashfree.request.side_effect=TimeoutError
        with self.assertRaises(TimeoutError): self.scope['send'](self.doc,self.op,'/split')
        with self.assertRaisesRegex(ValueError,'unconfirmed'): self.scope['send'](self.doc,self.op,'/split')
        self.cashfree.request.assert_called_once()

    def test_error_response_not_treated_as_success(self):
        self.cashfree.request.return_value={'status':'ERROR'}
        with self.assertRaises(ValueError): self.scope['send'](self.doc,self.op,'/split')
        self.assertEqual(self.op.status,'Unconfirmed')


class FulfilmentTests(unittest.TestCase):
    def test_pending_request_freezes_fulfilment(self):
        scope=functions('guard',enabled=lambda doc:True,state=lambda doc:{'status':'Awaiting approvals'},
            internal_cancel=SimpleNamespace(get=lambda:False),reject=reject)
        with self.assertRaisesRegex(ValueError,'Resolve'): scope['guard'](Doc())

    def test_no_release_before_delivery_or_during_request(self):
        provider=Mock()
        scope=functions('release_delivery',frappe=Mock(),cashfree=provider,state=lambda doc:{'status':'Awaiting approvals'},reject=reject)
        for status in ('Requested','Preparing','Out for Delivery','Cancelled','Delivered'):
            doc=Doc(status=status,delivered_at='2026-11-12',payment_status='Paid')
            scope['release_delivery'](doc)
        provider.request.assert_not_called()


class CancellationStageTests(unittest.TestCase):
    def setUp(self):
        self.doc = Doc(name='o',status='Accepted', gateway_refunded_amount=0)
        self.frappe=Mock();self.frappe.session.user='customer';self.frappe.get_doc.return_value=self.doc
        self.frappe.db.exists.return_value=False
        self.cashfree=Mock();self.cashfree.locked.return_value=self.doc
        self.cashfree.prepare_cancellation.return_value={'payment_id':'p','case':{'paid_amount':'100','amount':'100'}}
        self.case={};self.saved=[];self.cancel=Mock()
        self.scope=functions('initiate',frappe=self.frappe,cashfree=self.cashfree,
            access=lambda doc:'Customer',enabled=lambda doc:True, reject=reject,
            state=lambda doc:self.case,returns=SimpleNamespace(note=lambda x:x,state=lambda doc:{}),
            orders=Mock(),event=Mock(),save=lambda doc,case,status:self.saved.append((case,status)),cancel=self.cancel)

    def test_before_preparation_cancels(self):
        self.scope['initiate']('o','changed mind')
        self.cancel.assert_called_once()
        self.assertEqual(self.saved[0][0]['kind'],'Customer before preparing')

    def test_race_to_preparing_requires_both_approvals(self):
        def verify(doc):
            self.doc.status='Preparing'
            return {'payment_id':'p','case':{'paid_amount':'100','amount':'100'}}
        self.cashfree.prepare_cancellation.side_effect=verify
        self.scope['initiate']('o','changed mind')
        self.cancel.assert_not_called()
        self.assertEqual(self.saved[0][1],'Awaiting approvals')

    def test_owner_can_cancel_all_delivery_stages(self):
        self.scope['access']=lambda doc:'Shop'
        for status in ('Requested','Accepted','Preparing','Ready','Picked Up','Out for Delivery','Delivered'):
            self.doc.status=status
            self.scope['initiate']('o','shop unavailable')
            self.assertEqual(self.saved[-1][0]['kind'],'Shop cancellation')
        self.assertEqual(self.cancel.call_count,7)

    def test_customer_cannot_cancel_delivered(self):
        self.doc.status='Delivered'
        with self.assertRaisesRegex(ValueError,'no longer'):self.scope['initiate']('o','changed mind')
        self.cancel.assert_not_called()

    def test_duplicate_does_not_reverify_or_requeue(self):
        self.case={'status':'Refund pending'}
        self.scope['initiate']('o','same request')
        self.cashfree.prepare_cancellation.assert_not_called()
        self.cancel.assert_not_called()


class RefundIdempotencyTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        from urllib.parse import quote
        from local_commerce.services.return_rules import refund_evidence
        self.doc=Doc(name='o',gateway_order_id='go',gateway_profile='g')
        self.case={'paid_paise':10000,'payment_id':'p','amounts':{'refund_paise':8500}}
        rid='mp_'+hashlib.sha256(b'o').hexdigest()[:28]
        self.row={'order_id':'go','cf_payment_id':'p','refund_currency':'INR','refund_id':rid,
            'cf_refund_id':'cf','refund_amount':'85','refund_status':'SUCCESS'}
        self.op=Doc(status='Accepted')
        self.cashfree=Mock();self.cashfree.request.return_value=[self.row]
        self.send=Mock()
        self.scope=functions('queue_refund',hashlib=hashlib,quote=quote,refund_evidence=refund_evidence,
            operation=Mock(return_value=self.op),cashfree=self.cashfree,send=self.send,
            op_save=Mock(),event=Mock(),reject=reject)

    def test_success_is_not_posted_twice(self):
        self.assertTrue(self.scope['queue_refund'](self.doc,self.case))
        self.assertTrue(self.scope['queue_refund'](self.doc,self.case))
        self.send.assert_not_called()
        self.assertEqual(self.doc.gateway_refunded_amount,85)
        self.assertIn('confirmed',self.case['refund_status'])

    def test_other_pending_refund_blocks_overrefund(self):
        other=dict(self.row,refund_id='external',cf_refund_id='other',refund_amount='20',refund_status='PENDING')
        self.cashfree.request.return_value=[other]
        with self.assertRaises(ValueError):self.scope['queue_refund'](self.doc,self.case)
        self.send.assert_not_called()

    def test_refund_history_cannot_change_approved_amount(self):
        self.row['refund_amount']='90'
        with self.assertRaises(ValueError):self.scope['queue_refund'](self.doc,self.case)
        self.send.assert_not_called()
