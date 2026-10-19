"""Pure return/refund validation shared by requests and background processing."""
from local_commerce.services.payments.rules import money


def approved_amount(kind, entered, total, refunded):
    remaining = money(total) - money(refunded or 0)
    if kind not in ('Full', 'Partial'):
        raise ValueError('Choose full or partial refund')
    amount = remaining if kind == 'Full' else money(entered)
    if not amount.is_finite() or amount <= 0 or amount > remaining:
        raise ValueError('Refund must be positive and no more than the remaining paid amount')
    return amount


def refund_evidence(rows, snap, payment_id, refund_id, amount):
    """Validate all reservations, including pending refunds, before sending money."""
    if not isinstance(rows, list):
        raise ValueError('Refund history is unavailable; administrator review required')
    found, reserved, seen = None, money(0), set()
    for row in rows:
        if (row.get('order_id') != snap['order_id'] or row.get('refund_currency') != snap['currency']
                or str(row.get('cf_payment_id')) != str(payment_id)):
            raise ValueError('Refund history does not match the original payment')
        key = str(row.get('cf_refund_id') or '')
        if not key or key in seen:
            raise ValueError('Refund history contains missing or duplicate references')
        seen.add(key)
        value = money(row.get('refund_amount'))
        if not value.is_finite() or value <= 0:
            raise ValueError('Invalid refund history amount')
        status = row.get('refund_status')
        if status not in ('SUCCESS', 'PENDING', 'ONHOLD', 'FAILED', 'CANCELLED', 'ACTIVE'):
            raise ValueError('Unknown refund status; review in Cashfree before retrying')
        if row.get('refund_id') == refund_id:
            if value != money(amount) or found is not None:
                raise ValueError('The approved refund reference has changed')
            found = row
        elif status not in ('FAILED', 'CANCELLED'):
            reserved += value
    if reserved + money(amount) > money(snap['amount']):
        raise ValueError('Other refunds already use this payment balance; review in Cashfree')
    return found


def refund_payload(case, snap):
    amount = money(case['amount'])
    payload = dict(refund_id=case['refund_id'], refund_amount=float(amount),
        refund_note='Local dot return ' + case['refund_id'], refund_speed='STANDARD')
    if snap.get('settlement_mode', 'Easy Split') == 'Easy Split':
        share = money(money(snap['vendor_amount']) * amount / money(snap['amount']))
        if not snap.get('vendor_id') or share < 0 or share > amount:
            raise ValueError('Invalid original vendor split')
        payload['refund_splits'] = [dict(vendor_id=snap['vendor_id'], amount=float(share))] if share else []
    return payload
