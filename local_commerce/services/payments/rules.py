import base64
import hashlib
import hmac
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise ValueError("Invalid amount")
        return number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid amount") from None


def split_amounts(total, kind, value):
    total, value = money(total), money(value)
    if kind not in {"Percentage", "Fixed"} or (kind == "Percentage" and value > 100):
        raise ValueError("Choose a valid commission")
    commission = money(total * value / 100) if kind == "Percentage" else value
    if commission >= total:
        raise ValueError("Commission must be smaller than the payment")
    return total - commission, commission


def valid_signature(secret, timestamp, body, signature):
    if not secret or not timestamp or not signature:
        return False
    expected = base64.b64encode(
        hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


def successful_payment(remote, payments, order_id, amount, currency):
    if (
        remote.get("order_id") != order_id
        or remote.get("order_currency") != currency
        or money(remote.get("order_amount")) != money(amount)
    ):
        raise ValueError("Gateway order does not match the local order")
    for payment in payments:
        if payment.get("payment_status") == "SUCCESS":
            if (
                remote.get("order_status") != "PAID"
                or payment.get("payment_currency") != currency
                or money(payment.get("payment_amount")) != money(amount)
                or not payment.get("cf_payment_id")
            ):
                raise ValueError("Gateway payment amount or currency does not match")
            return str(payment["cf_payment_id"])
    return None
