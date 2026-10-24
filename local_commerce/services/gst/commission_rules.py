"""Pure signed ledger arithmetic; payment inputs still use non-negative money()."""
from decimal import Decimal, InvalidOperation
from local_commerce.services.payments.rules import money


def signed_money(value):
    try:
        value = Decimal(str(value))
        if not value.is_finite():
            raise ValueError('Invalid ledger amount')
        return money(abs(value)) * (-1 if value < 0 else 1)
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid ledger amount') from None
