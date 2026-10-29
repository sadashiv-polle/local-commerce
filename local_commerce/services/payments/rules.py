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


def payment_discount(payment):
    """Count only successfully redeemed, uniquely identified upfront discounts."""
    total = money(0)
    seen = set()
    offers = payment.get("payment_offers") or []
    if not isinstance(offers, list):
        raise ValueError("Invalid gateway offers")
    for offer in offers:
        redemption = offer.get("offer_redemption") or {}
        if redemption.get("redemption_status") != "SUCCESS":
            continue
        discount = money(redemption.get("discount_amount", 0))
        if not discount:
            continue
        identity = offer.get("offer_id")
        if offer.get("offer_type") != "DISCOUNT" or not identity or identity in seen:
            raise ValueError("Invalid or duplicate gateway discount")
        seen.add(identity)
        total += discount
    return total


def require_offer_accounting(doc):
    """Do not post gross cash or issue gross refunds for discounted receipts."""
    import json
    evidence = json.loads(doc.get("gateway_accounting_json") or "{}").get("payment_evidence", {})
    if money(evidence.get("discount_amount", 0)):
        raise ValueError("Cashfree discount requires accounting review before posting or refunding")


def successful_payment(remote, payments, order_id, amount, currency):
    if (
        remote.get("order_id") != order_id
        or remote.get("order_currency") != currency
        or money(remote.get("order_amount")) != money(amount)
    ):
        raise ValueError("Gateway order does not match the local order")
    if sum(p.get("payment_status") == "SUCCESS" for p in payments) > 1:
        raise ValueError("Multiple successful payments require reconciliation")
    for payment in payments:
        if payment.get("payment_status") == "SUCCESS":
            discount = payment_discount(payment)
            if discount and (payment.get("order_id") != order_id or payment.get("order_currency") != currency
                    or money(payment.get("order_amount")) != money(amount) or payment.get("is_captured") is not True):
                raise ValueError("Discounted payment needs captured, order-specific evidence")
            if (
                remote.get("order_status") != "PAID"
                or payment.get("payment_currency") != currency
                or money(payment.get("payment_amount")) + discount != money(amount)
                or (payment.get("order_id") is not None and payment["order_id"] != order_id)
                or (payment.get("order_amount") is not None and money(payment["order_amount"]) != money(amount))
                or (payment.get("order_currency") is not None and payment["order_currency"] != currency)
                or payment.get("is_captured") is False
                or not payment.get("cf_payment_id")
            ):
                raise ValueError("Gateway payment amount or currency does not match")
            return str(payment["cf_payment_id"])
    return None


def offer_receipt_allocation(doc):
    import json
    data = json.loads(doc.get("gateway_accounting_json") or "{}")
    payment = data.get("payment_evidence") or {}
    discount = money(payment.get("discount_amount", 0))
    if not discount:
        return None
    funding = data.get("offer_funding") or {}
    snap = json.loads(doc.gateway_snapshot)
    if (not funding.get("account") or not funding.get("provider") or not funding.get("evidence")
            or funding.get("payment_id") != doc.gateway_payment_id
            or money(funding.get("amount", 0)) != discount
            or snap.get("settlement_mode", "Easy Split") != "Direct merchant" or doc.get("gst_snapshot")
            or money(payment["payment_amount"]) + discount != money(snap["amount"])):
        raise ValueError("Confirm offer funding and accounting before posting this payment")
    return dict(account=funding["account"], payment_amount=str(money(payment["payment_amount"])), discount_amount=str(discount))
