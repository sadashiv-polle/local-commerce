"""Customer-safe refund history from authenticated provider evidence."""
import json
from .rules import money

LABELS = {'SUCCESS': 'Refund completed', 'PENDING': 'Processing', 'ONHOLD': 'Processing',
          'CANCELLED': 'Refund cancelled', 'FAILED': 'Refund failed'}


def merge(existing, rows, order_id, payment_id, currency, total, observed_at):
    history = {r['id']: r for r in json.loads(existing or '[]')}
    for row in rows:
        if (row.get('order_id') != order_id or str(row.get('cf_payment_id')) != str(payment_id)
                or row.get('refund_currency') != currency):
            raise ValueError('Refund identity does not match this payment')
        key = str(row.get('cf_refund_id') or '')
        amount = money(row.get('refund_amount'))
        if not key or amount <= 0 or amount > money(total):
            raise ValueError('Invalid refund amount or reference')
        old = history.get(key, {})
        if old and money(old['amount']) != amount:
            raise ValueError('Refund amount changed')
        status = str(row.get('refund_status') or '')
        if old.get('status') == 'SUCCESS':
            continue  # A stale response must never reverse a completed refund.
        events = list(old.get('events') or [])
        if not events or old.get('status') != status:
            events.append(dict(label=LABELS.get(status, 'Refund requested'), at=observed_at))
        history[key] = dict(events=events, id=key, amount=float(amount), currency=currency, status=status,
            label=LABELS.get(status, 'Refund requested'),
            requested_at=row.get('created_at') or old.get('requested_at'),
            first_seen_at=old.get('first_seen_at') or observed_at,
            updated_at=old.get('updated_at') if old.get('status') == status else observed_at)
    return list(history.values())


def summary(doc):
    rows = json.loads(doc.get('refund_tracking_json') or '[]')
    return rows
