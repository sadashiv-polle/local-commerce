import json
import unittest
from types import SimpleNamespace
from local_commerce.services.cancellation_refunds import prepare


class Doc(SimpleNamespace):
    def get(self, key):
        return getattr(self, key, None)


class CancellationRefundTests(unittest.TestCase):
    def setUp(self):
        self.doc = Doc(name='LC-1', gateway_profile='gateway', gateway_order_id='provider1',
                       gateway_snapshot=json.dumps(dict(amount='210', currency='INR', settlement_mode='Direct merchant')))
        self.payment = dict(payment_amount=160)

    def refund(self, amount=50, status='SUCCESS'):
        return dict(order_id='provider1', cf_payment_id='pay1', refund_currency='INR',
                    cf_refund_id='ref1', refund_id='external', refund_amount=amount, refund_status=status)

    def test_discount_refunds_only_cash_paid_with_stable_identity(self):
        result = prepare(self.doc, 'pay1', self.payment, [])
        self.assertEqual(result['case']['payload']['refund_amount'], 160)
        self.assertEqual(result['case']['paid_amount'], '160.00')
        self.assertEqual(result, prepare(self.doc, 'pay1', self.payment, []))

    def test_subtract_completed_refunds(self):
        result = prepare(self.doc, 'pay1', self.payment, [self.refund()])
        self.assertEqual(result['case']['payload']['refund_amount'], 110)
        result = prepare(self.doc, 'pay1', self.payment, [self.refund(160)])
        self.assertNotIn('payload', result['case'])
        self.assertEqual(result['case']['amount'], '0.00')

    def test_reject_pending_unknown_duplicate_and_wrong_payment(self):
        for rows in ([self.refund(status='PENDING')], [self.refund(status='UNKNOWN')],
                     [self.refund(), self.refund()], [dict(self.refund(), cf_payment_id='other')],
                     [self.refund(170)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                prepare(self.doc, 'pay1', self.payment, rows)

    def test_incomplete_history_cannot_refund_again(self):
        self.doc.gateway_refunded_amount = 50
        with self.assertRaises(ValueError):
            prepare(self.doc, 'pay1', self.payment, [])

    def test_split_uses_original_allocation(self):
        self.doc.gateway_snapshot = json.dumps(dict(amount=210, currency='INR', vendor_id='vendor', vendor_amount=189))
        result = prepare(self.doc, 'pay1', self.payment, [])
        self.assertEqual(result['case']['payload']['refund_splits'], [dict(vendor_id='vendor', amount=144)])

class CancellationWorkerTests(unittest.TestCase):
    def setUp(self):
        import ast
        from pathlib import Path
        from unittest.mock import Mock
        from urllib.parse import quote
        from local_commerce.services.return_rules import refund_evidence
        self.case = dict(status='Refund queued', purpose='Cancellation', paid_amount='160',
                         amount='160', payment_id='pay1', refund_id='cancel1',
                         payload=dict(refund_id='cancel1', refund_amount=160))
        self.doc = Doc(status='Cancelled', gateway_payment_id='pay1', gateway_order_id='order1',
                       gateway_profile='gateway', gateway_snapshot=json.dumps(dict(amount=210, currency='INR')))
        self.cashfree = Mock()
        self.cashfree.payment_order.return_value = self.doc
        self.cashfree.locked.return_value = self.doc
        self.frappe = Mock()
        self.guard = Mock(side_effect=ValueError('Offer accounting unresolved'))
        def save(doc, case, status):
            case['status'] = status
        def reject(message):
            raise ValueError(message)
        scope = dict(cashfree=self.cashfree, frappe=self.frappe, state=lambda doc: self.case,
                     lock=lambda order: self.doc, save=save, reject=reject, json=json, quote=quote,
                     require_offer_accounting=self.guard, refund_evidence=refund_evidence)
        tree = ast.parse(Path('local_commerce/services/returns.py').read_text())
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                                    and n.name == 'process'], type_ignores=[]), 'returns.py', 'exec'), scope)
        self.process = scope['process']
        self.row = dict(order_id='order1', cf_payment_id='pay1', refund_currency='INR',
                        cf_refund_id='cf1', refund_id='cancel1', refund_amount=160, refund_status='PENDING')

    def test_existing_refund_is_polled_without_duplicate_post(self):
        self.cashfree.request.return_value = [self.row]
        self.process('LC-1')
        self.assertEqual(self.cashfree.request.call_count, 1)
        self.assertEqual(self.cashfree.request.call_args.args[1], 'GET')
        self.assertEqual(self.case['status'], 'Refund processing')
        self.guard.assert_not_called()
        self.cashfree.sync.assert_called_once_with('LC-1', authorize=False)

    def test_new_refund_posts_committed_payload_with_stable_key(self):
        self.cashfree.request.side_effect = [[], {}, [self.row]]
        self.process('LC-1')
        post = self.cashfree.request.call_args_list[1]
        self.assertEqual(post.args[1], 'POST')
        self.assertEqual(post.args[3]['refund_amount'], 160)
        self.assertEqual(post.kwargs['key'], 'order1:cancel1')

    def test_uncertain_post_keeps_identity_for_admin_retry(self):
        self.cashfree.request.side_effect = [[], TimeoutError()]
        self.process('LC-1')
        self.assertEqual(self.case['status'], 'Needs review')
        self.assertEqual(self.case['refund_id'], 'cancel1')
        self.case['status'] = 'Refund queued'
        self.cashfree.request.reset_mock(side_effect=True)
        self.cashfree.request.return_value = [self.row]
        self.process('LC-1')
        self.assertEqual(self.cashfree.request.call_count, 1)
        self.assertEqual(self.case['status'], 'Refund processing')

    def test_no_money_movement_if_order_no_longer_cancelled(self):
        self.doc.status = 'Accepted'
        self.process('LC-1')
        self.cashfree.request.assert_not_called()
        self.assertEqual(self.case['status'], 'Needs review')
