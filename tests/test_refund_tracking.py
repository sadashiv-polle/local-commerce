import json
import unittest
from local_commerce.services.payments.refund_tracking import merge


class RefundTrackingTests(unittest.TestCase):
    def row(self, **changes):
        return dict(dict(cf_refund_id='r1', cf_payment_id='p1', order_id='o1',
                         refund_currency='INR', refund_amount=100, refund_status='PENDING',
                         created_at='2026-10-12T10:00:00+05:30'), **changes)

    def sync(self, rows, old='[]', at='2026-10-12 10:10:00'):
        return merge(old, rows, 'o1', 'p1', 'INR', 350, at)

    def test_processing_then_completed_preserves_history(self):
        pending = self.sync([self.row()])
        done = self.sync([self.row(refund_status='SUCCESS')], json.dumps(pending), '2026-10-12 10:20:00')
        self.assertEqual(done[0]['label'], 'Refund completed')
        self.assertEqual([r['label'] for r in done[0]['events']], ['Processing', 'Refund completed'])
        self.assertEqual(done[0]['requested_at'], pending[0]['requested_at'])

    def test_replay_and_stale_pending_do_not_reverse_completion(self):
        done = self.sync([self.row(refund_status='SUCCESS')])
        self.assertEqual(self.sync([self.row()], json.dumps(done)), done)
        self.assertEqual(self.sync([self.row(refund_status='SUCCESS')], json.dumps(done)), done)

    def test_wrong_payment_order_currency_rejected(self):
        for changes in [dict(cf_payment_id='other'), dict(order_id='other'), dict(refund_currency='USD')]:
            with self.assertRaises(ValueError): self.sync([self.row(**changes)])

    def test_invalid_or_changed_amount_rejected(self):
        for amount in [0, -1, 351, 'NaN']:
            with self.assertRaises(ValueError): self.sync([self.row(refund_amount=amount)])
        old = self.sync([self.row()])
        with self.assertRaises(ValueError): self.sync([self.row(refund_amount=200)], json.dumps(old))

    def test_failed_and_unknown_not_success(self):
        self.assertEqual(self.sync([self.row(refund_status='FAILED')])[0]['label'], 'Refund failed')
        self.assertNotEqual(self.sync([self.row(refund_status='UNKNOWN')])[0]['label'], 'Refund completed')

    def test_missing_provider_date_is_not_invented(self):
        row = self.sync([self.row(created_at=None)])[0]
        self.assertIsNone(row['requested_at'])
        self.assertTrue(row['first_seen_at'])
