"""Offer evidence and reimbursement tracking, separate from customer payment status."""

import json
from urllib.parse import quote

import frappe

from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject

from .rules import money


def state(doc):
    return json.loads(doc.get("gateway_accounting_json") or "{}")


def summary(doc, private=False):
    data = state(doc)
    payment = data.get("payment_evidence", {})
    discount = money(payment.get("discount_amount", 0))
    if not discount:
        return None
    result = {
        key: payment.get(key)
        for key in ("order_amount", "payment_amount", "discount_amount", "currency")
    }
    result["offers"] = [
        {"id": offer.get("offer_id"), "title": (offer.get("offer_meta") or {}).get("offer_title")}
        for offer in payment.get("offers", [])
        if (offer.get("offer_redemption") or {}).get("redemption_status") == "SUCCESS"
    ]
    if private:
        funding = data.get("offer_funding", {})
        settlement = data.get("offer_settlement", {})
        result.update(
            funding=funding,
            settlement=settlement,
            reimbursement_status="Confirmed by linked journal"
            if data.get("offer_reimbursement")
            else "Unconfirmed",
            reimbursement=data.get("offer_reimbursement"),
            unresolved_amount=str(discount if not data.get("offer_reimbursement") else money(0)),
        )
    return result


def settlement_observation(payload, payment, order_id, payment_id):
    """Order-specific settlement observation; never infer an offer sponsor from net cash."""
    order = payload.get("order_details") or {}
    paid = payload.get("payment_details") or {}
    settled = payload.get("settlement_details") or {}
    if (
        order.get("order_id") != order_id
        or order.get("order_currency") != payment["currency"]
        or money(order.get("order_amount")) != money(payment["order_amount"])
        or str(paid.get("cf_payment_id")) != str(payment_id)
        or paid.get("payment_currency") != payment["currency"]
        or money(paid.get("payment_amount")) != money(payment["payment_amount"])
    ):
        raise ValueError("Settlement does not match the verified customer payment")
    if settled.get("status") != "SUCCESS":
        return {"status": "Awaiting settlement"}
    if (
        settled.get("settlement_currency") != payment["currency"]
        or paid.get("charge_type") != "PREPAID"
        or paid.get("charged_to") != "MERCHANT"
    ):
        raise ValueError("Settlement currency or fee allocation needs review")
    reference, utr, date = (
        settled.get(k) for k in ("cf_settlement_id", "settlement_utr", "settlement_processed_on")
    )
    if not reference or not utr or utr == "N/A" or not date or date == "N/A":
        raise ValueError("Completed settlement reference, UTR and date are required")
    fees = sum(
        (
            money(paid[k])
            for k in (
                "pg_service_charge",
                "split_service_charge",
                "pg_service_tax",
                "split_service_tax",
            )
        ),
        money(0),
    )
    net = money(paid["settlement_amount"])
    gross = net + fees
    extra = gross - money(payment["payment_amount"])
    if extra < 0 or extra > money(payment["discount_amount"]):
        raise ValueError("Settlement has unexplained adjustments; manual reconciliation required")
    return dict(
        status="Provider settlement observed",
        reference=str(reference),
        utr=str(utr),
        date=str(date),
        net=str(net),
        fees=str(fees),
        gross=str(gross),
        amount_above_customer_payment=str(extra),
        note="Settlement evidence does not identify the offer funder. Confirm allocation against the bank statement.",
    )


def check_settlement(order):
    require_platform()
    from . import cashfree

    cashfree.begin_operation(order)
    doc = cashfree.payment_order(order)
    data = state(doc)
    payment = data.get("payment_evidence", {})
    if not money(payment.get("discount_amount", 0)):
        reject("Verify a discounted payment first")
    snap = json.loads(doc.gateway_snapshot)
    if snap.get("settlement_mode", "Easy Split") != "Direct merchant":
        reject(
            "Easy Split offer funding needs the vendor and platform settlement reports; do not infer it from the vendor payout alone"
        )
    payload = cashfree.request(
        doc.gateway_profile,
        "GET",
        "/orders/" + quote(doc.gateway_order_id, safe="") + "/settlements",
        api_version="2026-01-01",
    )
    observation = settlement_observation(
        payload, payment, doc.gateway_order_id, doc.gateway_payment_id
    )
    doc = cashfree.locked(order)
    data = state(doc)
    observation["checked_at"] = str(frappe.utils.now_datetime())
    data["offer_settlement"] = observation
    doc.gateway_accounting_json = json.dumps(data)
    cashfree.save(doc)
    return summary(doc, private=True)


def approve_funding(order, provider, evidence, account):
    """Explicit per-order funding confirmation, never guessed from an offer code."""
    require_platform()
    from . import accounting, cashfree

    cashfree.begin_operation(order)
    doc = cashfree.locked(order)
    data = state(doc)
    payment = data.get("payment_evidence", {})
    if doc.payment_status != "Paid" or not money(payment.get("discount_amount", 0)):
        reject("A verified discounted payment is required")
    if doc.status == "Cancelled" or doc.payment_entry or doc.gateway_refunded_amount:
        reject("Cancelled, refunded or already posted orders need manual accounting review")
    snap = json.loads(doc.gateway_snapshot)
    if snap.get("settlement_mode", "Easy Split") != "Direct merchant" or doc.get("gst_snapshot"):
        reject(
            "Easy Split and marketplace GST offers require vendor allocation and tax review before posting"
        )
    provider, evidence = str(provider).strip(), str(evidence).strip()
    if not 3 <= len(provider) <= 140 or not 10 <= len(evidence) <= 1000:
        reject(
            "Name the confirmed funder and provide its written funding agreement or support reference"
        )
    company = frappe.db.get_value("Sales Order", doc.sales_order, "company")
    accounting.account(account, company, "Asset")
    account_doc = frappe.get_doc("Account", account)
    if (
        account_doc.account_type in {"Bank", "Cash", "Receivable", "Payable"}
        or account == snap["clearing_account"]
    ):
        reject(
            "Select a separate non-bank offer reimbursement asset account, without a party account type"
        )
    funding = dict(
        provider=provider,
        evidence=evidence,
        account=account,
        amount=payment["discount_amount"],
        payment_id=doc.gateway_payment_id,
        approved_by=frappe.session.user,
        approved_at=str(frappe.utils.now_datetime()),
    )
    data.setdefault("offer_funding_history", []).append(funding)
    data["offer_funding"] = funding
    doc.gateway_accounting_json = json.dumps(data)
    cashfree.save(doc)
    return {
        "status": "Funding confirmation saved. Retry verification to post the receipt and accept the order."
    }


def link_reimbursement(order, journal):
    """Link a submitted, dedicated receipt journal; do not mark a promise as received."""
    require_platform()
    from . import accounting, cashfree

    cashfree.begin_operation(order)
    doc = cashfree.locked(order)
    data = state(doc)
    funding = data.get("offer_funding") or {}
    if not funding or not doc.payment_entry:
        reject("Post the verified receipt and funding receivable first")
    if data.get("offer_reimbursement"):
        if data["offer_reimbursement"]["journal"] != journal:
            reject("A reimbursement is already linked; review the original journal")
        accounting.submitted("Journal Entry", journal)
        return summary(doc, private=True)
    frappe.db.sql("select name from `tabJournal Entry` where name=%s for update", journal)
    accounting.submitted("Journal Entry", journal)
    receipt = frappe.get_doc("Journal Entry", journal)
    company = frappe.db.get_value("Sales Order", doc.sales_order, "company")
    accounting.account(funding["account"], company, "Asset")
    amount = money(funding["amount"])
    if (
        receipt.company != company
        or not receipt.cheque_no
        or doc.name not in (receipt.user_remark or "")
    ):
        reject(
            "Use a dedicated journal in this company with a bank reference and this LC Order ID in its remarks"
        )
    if len(receipt.accounts) != 2:
        reject("Use a dedicated two-line reimbursement journal to prevent duplicate allocations")
    credit = [
        r
        for r in receipt.accounts
        if r.account == funding["account"]
        and money(r.credit_in_account_currency) == amount
        and not r.debit_in_account_currency
    ]
    debit = [
        r
        for r in receipt.accounts
        if money(r.debit_in_account_currency) == amount and not r.credit_in_account_currency
    ]
    if len(credit) != 1 or len(debit) != 1:
        reject("Journal must debit the bank and credit the offer receivable for the full discount")
    accounting.account(debit[0].account, company, "Asset", bank=True)
    if debit[0].account == json.loads(doc.gateway_snapshot)["clearing_account"]:
        reject("Use the actual receiving bank, not the Cashfree clearing account")
    # A journal is exclusively allocated to one order, including concurrent requests.
    frappe.db.sql("select name from `tabJournal Entry` where name=%s for update", journal)
    others = frappe.get_all(
        "LC Order",
        filters={"payment_method": "Cashfree", "name": ["!=", doc.name]},
        fields=["gateway_accounting_json"],
        limit_page_length=0,
    )
    if any(
        json.loads(r.gateway_accounting_json or "{}").get("offer_reimbursement", {}).get("journal")
        == journal
        for r in others
    ):
        reject("This reimbursement journal is already allocated to another order")
    data["offer_reimbursement"] = dict(
        journal=journal,
        amount=str(amount),
        bank_reference=receipt.cheque_no,
        verified_by=frappe.session.user,
        verified_at=str(frappe.utils.now_datetime()),
    )
    doc.gateway_accounting_json = json.dumps(data)
    cashfree.save(doc)
    return summary(doc, private=True)
