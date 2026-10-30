"""Queue a verified cancellation refund in the same transaction as cancellation."""
import hashlib
import json

from local_commerce.services.payments.rules import money
from local_commerce.services.return_rules import refund_evidence, refund_payload


def prepare(doc, payment_id, payment, rows):
    snap = json.loads(doc.gateway_snapshot)
    paid = money(payment['payment_amount'])
    refund_id = 'cancel' + hashlib.sha256(doc.name.encode()).hexdigest()[:28]
    # Verify identity, status and duplicate references before using any balance.
    check = dict(snap, order_id=doc.gateway_order_id, amount=str(paid))
    refund_evidence(rows, check, payment_id, refund_id, 0)
    if any(r['refund_status'] not in ('SUCCESS', 'FAILED', 'CANCELLED') for r in rows):
        raise ValueError('Another refund is processing. Refresh its status before cancellation.')
    refunded = sum((money(r['refund_amount']) for r in rows if r['refund_status'] == 'SUCCESS'), money(0))
    if refunded < money(doc.get('gateway_refunded_amount') or 0):
        raise ValueError('Refund history is incomplete. Retry verification before cancellation.')
    amount = paid - refunded
    if amount < 0:
        raise ValueError('Refunds exceed the customer payment')
    case = dict(kind='Full', purpose='Cancellation', amount=str(amount),
                paid_amount=str(paid), refund_id=refund_id, payment_id=payment_id)
    if amount:
        case['payload'] = refund_payload(case, snap)
        case['payload']['refund_note'] = 'Local dot cancellation ' + refund_id
    return dict(identity=(doc.name, doc.gateway_profile, doc.gateway_order_id, doc.gateway_snapshot),
                payment_id=payment_id, case=case)


def queue(doc, evidence):
    import frappe
    from local_commerce.services import returns

    if returns.state(doc):
        raise ValueError('An existing return or refund case needs review before cancellation')
    case = evidence['case']
    case.update(reason=doc.reason, requested_by=frappe.session.user,
                requested_at=str(frappe.utils.now_datetime()),
                decision_note='Automatic refund following order cancellation')
    doc.gateway_payment_id = evidence['payment_id']
    doc.payment_status = 'Paid' if money(case['amount']) else 'Refunded'
    # Persist only: orders.change saves the order and queues work after commit.
    case['status'] = 'Refund queued' if money(case['amount']) else 'Refund completed'
    case['updated_at'] = case['requested_at']
    case['events'] = [dict(status=case['status'], at=case['updated_at'])]
    doc.return_request_json = json.dumps(case)
    doc.return_status = case['status']
    if money(case['amount']):
        frappe.enqueue('local_commerce.services.returns.process', order=doc.name, enqueue_after_commit=True)
