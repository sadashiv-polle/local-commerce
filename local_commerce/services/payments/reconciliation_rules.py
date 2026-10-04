"""Fail closed when provider evidence is incomplete or does not balance."""

from .rules import money


def refunds_for_order(rows, order_id, payment_id, currency, total):
    result = {}
    for row in rows:
        if row.get("refund_status") != "SUCCESS":
            continue
        if row.get("order_id") != order_id or row.get("refund_currency") != currency:
            raise ValueError("Refund order or currency does not match")
        if str(row.get("cf_payment_id")) != str(payment_id):
            raise ValueError("Refund payment does not match")
        key = str(row.get("cf_refund_id") or "")
        amount = money(row.get("refund_amount"))
        if not key or amount <= 0:
            raise ValueError("Refund reference and positive amount are required")
        if key in result and money(result[key]["refund_amount"]) != amount:
            raise ValueError("Refund amount changed")
        result[key] = row
    if sum((money(r["refund_amount"]) for r in result.values()), money(0)) > money(total):
        raise ValueError("Refunds exceed the original payment")
    return result


def settlement_evidence(payload, snap, order_id, payment_id):
    """Normalize only completed, order-specific direct/vendor settlements.

    A batch settlement amount is never used as an individual order amount.
    Unexplained adjustments and postpaid fees require review, not guessed postings.
    """
    if snap.get("settlement_mode", "Easy Split") == "Easy Split":
        if payload.get("cursor"):
            raise ValueError("Incomplete vendor settlement result; review pagination")
        rows = [
            r
            for r in payload.get("data", [])
            if r.get("merchant_order_id") == order_id
            and r.get("merchant_vendor_id") == snap["vendor_id"]
            and r.get("entity_type") == "vendor_commission"
            and r.get("sale_type") == "CREDIT"
        ]
        if not rows or any(r.get("settled") != "YES" for r in rows):
            return None
        if len(rows) != 1:
            raise ValueError("Multiple vendor settlement allocations require review")
        r = rows[0]
        if r.get("currency") != snap["currency"] or money(r["amount"]) != money(
            snap["vendor_amount"]
        ):
            raise ValueError("Vendor settlement amount or currency changed")
        fee = money(r["vendor_pg_service_charge"]) + money(r["vendor_split_service_charges"])
        tax = money(r["vendor_pg_service_tax"]) + money(r["vendor_split_service_tax"])
        gross = money(r["amount"])
        net = gross - fee - tax
        reference, utr, date = (
            r.get("vendor_settlement_id"),
            r.get("vendor_settlement_utr"),
            r.get("vendor_settlement_time"),
        )
    else:
        order, payment, settled = (
            payload.get(k, {}) for k in ("order_details", "payment_details", "settlement_details")
        )
        if (
            order.get("order_id") != order_id
            or order.get("order_currency") != snap["currency"]
            or money(order.get("order_amount")) != money(snap["amount"])
            or str(payment.get("cf_payment_id")) != str(payment_id)
            or payment.get("payment_currency") != snap["currency"]
            or money(payment.get("payment_amount")) != money(snap["amount"])
        ):
            raise ValueError("Settlement does not match the verified payment")
        if settled.get("status") != "SUCCESS":
            return None
        if settled.get("settlement_currency") != snap["currency"]:
            raise ValueError("Settlement currency changed")
        if payment.get("charge_type") != "PREPAID" or payment.get("charged_to") != "MERCHANT":
            raise ValueError("Postpaid or customer-paid charges require separate reconciliation")
        fee = money(payment["pg_service_charge"]) + money(payment["split_service_charge"])
        tax = money(payment["pg_service_tax"]) + money(payment["split_service_tax"])
        gross, net = money(snap["amount"]), money(payment["settlement_amount"])
        reference, utr, date = (
            settled.get("cf_settlement_id"),
            settled.get("settlement_utr"),
            settled.get("settlement_processed_on"),
        )
    if net < 0 or net + fee + tax != gross:
        raise ValueError("Settlement net amount and charges do not balance")
    if not reference or not utr or str(utr) == "N/A" or not date or str(date) == "N/A":
        raise ValueError("Completed settlement reference, UTR and date are required")
    return dict(
        reference=str(reference),
        utr=str(utr),
        date=str(date),
        gross=str(gross),
        net=str(net),
        fee=str(fee),
        tax=str(tax),
    )
