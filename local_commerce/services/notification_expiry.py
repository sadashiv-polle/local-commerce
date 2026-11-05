"""Inbox visibility; retained records still support campaign reporting."""
from datetime import timedelta
from local_commerce.services.shop_hours import normalize


def expires_at(created, opening_hours=None):
    expiry = created + timedelta(hours=10)
    try:
        schedule = normalize(opening_hours)
    except (ValueError, TypeError):
        return expiry
    if not schedule:
        return expiry
    midnight = created.replace(hour=0, minute=0, second=0, microsecond=0)
    # Include yesterday's overnight opening period.
    for offset in (-1, 0):
        day = midnight + timedelta(days=offset)
        row = schedule[day.weekday()]
        if not row['enabled']:
            continue
        h, m = map(int, row['opens'].split(':'))
        opened = day + timedelta(hours=h, minutes=m)
        h, m = map(int, row['closes'].split(':'))
        closed = day + timedelta(hours=h, minutes=m)
        if closed <= opened:
            closed += timedelta(days=1)
        if opened <= created < closed:
            return min(expiry, closed)
    return expiry
