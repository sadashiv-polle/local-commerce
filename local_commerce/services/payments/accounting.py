"""Verified provider events -> native ERPNext accounting, within the order mutex.

No commits here. Native documents and the order's event map commit atomically.
Refunds are financial only: physical inventory returns are a separate workflow.
"""

import json
from contextlib import contextmanager
from urllib.parse import quote

import frappe

from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject

from .reconciliation_rules import refunds_for_order, settlement_evidence
from .rules import money


@contextmanager
def posting():
    from local_commerce.services.orders import _order_operation
    from local_commerce.services.owner import _owner_operation

    user = frappe.session.user
    order_token, owner_token = _order_operation.set(True), _owner_operation.set(True)
    try:
        frappe.set_user("Administrator")
        yield
    finally:
        frappe.set_user(user)
        _order_operation.reset(order_token)
        _owner_operation.reset(owner_token)


def state(doc):
    return json.loads(doc.get("gateway_accounting_json") or "{}")


def persist(doc, data):
    from .cashfree import save

    doc.gateway_accounting_json = frappe.as_json(data)
    save(doc)


def account(name, company, root, bank=False):
    row = frappe.get_doc("Account", name)
    if (
        row.company != company
        or row.root_type != root
        or row.disabled
        or row.is_group
        or row.account_currency != "INR"
        or (bank and row.account_type != "Bank")
    ):
        reject("Select an active INR account in this shop Company")
    return name


def submitted(doctype, name):
    if not name or frappe.db.get_value(doctype, name, "docstatus") != 1:
        reject(f"The linked {doctype} is missing or cancelled; administrator review is required")


def book_refunds(doc, rows):
    """Automatic full credit; partial refunds use an admin-selected native credit note."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

    snap, data = json.loads(doc.gateway_snapshot), state(doc)
    refunds = refunds_for_order(
        rows, doc.gateway_order_id, doc.gateway_payment_id, snap["currency"], snap["amount"]
    )
    recorded = data.setdefault("refunds", {})
    # A historical amount without event IDs cannot safely be posted automatically.
    if sum((money(r["refund_amount"]) for r in refunds.values()), money(0)) < money(
        doc.gateway_refunded_amount
    ):
        reject("Cashfree has not returned the complete refund history. Retry verification")
    if not doc.sales_invoice and not doc.payment_entry:
        return book_unbilled_refund(doc, refunds, snap, data)
    submitted("Sales Invoice", doc.sales_invoice)
    submitted("Payment Entry", doc.payment_entry)
    invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)
    if invoice.currency != "INR" or money(invoice.grand_total) != money(snap["amount"]):
        reject("Original invoice does not match the Cashfree payment")
    account(snap["clearing_account"], invoice.company, "Asset", bank=True)
    with posting():
        for key, row in refunds.items():
            amount = money(row["refund_amount"])
            if key in recorded:
                if money(recorded[key]["amount"]) != amount:
                    reject("Previously posted refund amount changed")
                submitted("Sales Invoice", recorded[key]["credit_note"])
                submitted("Payment Entry", recorded[key]["payment_entry"])
                if recorded[key].get("commission_journal"):
                    submitted("Journal Entry", recorded[key]["commission_journal"])
                continue
            credit_name = data.get("refund_credit_notes", {}).get(key)
            if credit_name:
                credit = frappe.get_doc("Sales Invoice", credit_name)
            elif amount == money(snap["amount"]) and not recorded:
                # Do not duplicate a credit already created outside this workflow.
                if frappe.db.exists(
                    "Sales Invoice", {"return_against": invoice.name, "docstatus": ["!=", 2]}
                ):
                    reject("A credit note already exists. Select it in Cashfree accounting")
                credit = make_sales_return(invoice.name)
                credit.update_stock = 0
                credit.update_outstanding_for_self = 1
                credit.lc_order = doc.name
                credit.posting_date = frappe.utils.nowdate()
                credit.set_posting_time = 0
                credit.insert(ignore_permissions=True)
                if money(abs(credit.grand_total)) != amount:
                    reject("Credit note total does not match the verified refund")
                credit.submit()
                credit.reload()
            else:
                reject("Partial refund: select its submitted credit note in Cashfree accounting")
            if (
                credit.docstatus != 1
                or not credit.is_return
                or credit.return_against != invoice.name
                or credit.company != invoice.company
                or credit.customer != invoice.customer
                or credit.currency != invoice.currency
                or not credit.update_outstanding_for_self
                or money(abs(credit.grand_total)) != amount
                or credit.outstanding_amount >= 0
                or money(abs(credit.outstanding_amount)) != amount
            ):
                reject("Select an unpaid credit note for this invoice, matching the refund exactly")
            payment = get_payment_entry(
                "Sales Invoice", credit.name, bank_account=snap["clearing_account"]
            )
            payment.lc_order = doc.name
            payment.reference_no = key
            payment.reference_date = frappe.utils.nowdate()
            payment.mode_of_payment = snap["mode_of_payment"]
            payment.insert(ignore_permissions=True)
            if payment.payment_type != "Pay" or money(payment.paid_amount) != amount:
                reject("Refund Payment Entry does not match the provider amount")
            payment.submit()
            reversal = money(0)
            reversal_journal = None
            if money(snap.get("commission") or 0):
                splits = row.get("refund_splits") or []
                vendor = [r for r in splits if r.get("vendor_id") == snap.get("vendor_id")]
                if len(vendor) != 1 or any(
                    r.get("vendor_id") != snap.get("vendor_id") for r in splits
                ):
                    reject("Cashfree refund split evidence is required to reverse commission")
                vendor_debit = money(vendor[0].get("amount"))
                if vendor_debit > amount:
                    reject("Vendor refund exceeds the customer refund")
                reversal = amount - vendor_debit
                already = sum(
                    (money(r.get("commission_reversed", 0)) for r in recorded.values()), money(0)
                )
                if already + reversal > money(snap["commission"]):
                    reject("Refund commission reversal exceeds the original commission")
                if reversal:
                    account(snap["commission_account"], invoice.company, "Expense")
                    journal = frappe.get_doc(
                        dict(
                            doctype="Journal Entry",
                            voucher_type="Journal Entry",
                            company=invoice.company,
                            posting_date=frappe.utils.nowdate(),
                            user_remark="Cashfree refund commission " + key + " for " + doc.name,
                            accounts=[
                                dict(
                                    account=snap["clearing_account"],
                                    debit_in_account_currency=float(reversal),
                                ),
                                dict(
                                    account=snap["commission_account"],
                                    credit_in_account_currency=float(reversal),
                                    cost_center=frappe.db.get_value(
                                        "LC Shop", doc.shop, "cost_center"
                                    ),
                                ),
                            ],
                        )
                    ).insert(ignore_permissions=True)
                    journal.submit()
                    reversal_journal = journal.name
            recorded[key] = {
                "amount": str(amount),
                "credit_note": credit.name,
                "payment_entry": payment.name,
                "commission_reversed": str(reversal),
                "commission_journal": reversal_journal,
            }
        persist(doc, data)


def book_unbilled_refund(doc, refunds, snap, data):
    """A fully refunded checkout that never became a sale has no revenue to credit."""
    from erpnext.accounts.party import get_party_account

    total = sum((money(r["refund_amount"]) for r in refunds.values()), money(0))
    if (
        total != money(snap["amount"])
        or doc.status not in {"Requested", "Cancelled"}
        or money(snap.get("commission") or 0)
    ):
        reject("Unbilled partial refund requires review of the original receipt first")
    evidence = {key: str(money(row["refund_amount"])) for key, row in refunds.items()}
    old = data.get("unbilled_refund")
    if old:
        if old["refunds"] != evidence:
            reject("Unbilled refund evidence changed")
        for journal in old["journals"]:
            submitted("Journal Entry", journal)
        return
    if frappe.db.exists(
        "Payment Entry",
        {
            "reference_no": doc.gateway_payment_id,
            "docstatus": ["!=", 2],
        },
    ):
        reject("An existing payment receipt needs review before posting an unbilled refund")
    so = frappe.get_doc("Sales Order", doc.sales_order)
    if so.currency != "INR":
        reject("Refund currency does not match the original checkout")
    clearing = account(snap["clearing_account"], so.company, "Asset", bank=True)
    with posting():
        receivable = get_party_account("Customer", so.customer, so.company)
        account(receivable, so.company, "Asset")
        receipt = frappe.get_doc(
            dict(
                doctype="Journal Entry",
                voucher_type="Journal Entry",
                company=so.company,
                posting_date=frappe.utils.nowdate(),
                user_remark="Cashfree unbilled receipt "
                + doc.gateway_payment_id
                + " for "
                + doc.name,
                accounts=[
                    dict(account=clearing, debit_in_account_currency=float(total)),
                    dict(
                        account=receivable,
                        party_type="Customer",
                        party=so.customer,
                        credit_in_account_currency=float(total),
                    ),
                ],
            )
        ).insert(ignore_permissions=True)
        receipt.submit()
        refund = frappe.get_doc(
            dict(
                doctype="Journal Entry",
                voucher_type="Journal Entry",
                company=so.company,
                posting_date=frappe.utils.nowdate(),
                user_remark="Cashfree unbilled full refund for " + doc.name,
                accounts=[
                    dict(
                        account=receivable,
                        party_type="Customer",
                        party=so.customer,
                        debit_in_account_currency=float(total),
                        reference_type="Journal Entry",
                        reference_name=receipt.name,
                    ),
                    dict(account=clearing, credit_in_account_currency=float(total)),
                ],
            )
        ).insert(ignore_permissions=True)
        refund.submit()
        data["unbilled_refund"] = {"refunds": evidence, "journals": [receipt.name, refund.name]}
        persist(doc, data)


def reconcile_settlement(order):
    """One per-order allocation, not the entire provider settlement batch."""
    from . import cashfree

    cashfree.begin_operation(order)
    doc = cashfree.payment_order(order)
    snap = json.loads(doc.gateway_snapshot)
    if not doc.payment_entry or not doc.gateway_payment_id:
        if state(doc).get("unbilled_refund"):
            for journal in state(doc)["unbilled_refund"]["journals"]:
                submitted("Journal Entry", journal)
            return {"status": "Unbilled receipt and full refund accounted"}
        reject("Verify and post the payment before reconciling its settlement")
    if snap.get("settlement_mode", "Easy Split") == "Easy Split":
        payload = cashfree.request(
            doc.gateway_profile,
            "POST",
            "/split/order/vendor/recon",
            {"filters": {"order_ids": [doc.gateway_order_id]}},
            api_version="2026-01-01",
        )
    else:
        payload = cashfree.request(
            doc.gateway_profile,
            "GET",
            "/orders/" + quote(doc.gateway_order_id, safe="") + "/settlements",
            api_version="2026-01-01",
        )
    evidence = settlement_evidence(payload, snap, doc.gateway_order_id, doc.gateway_payment_id)
    doc = cashfree.locked(order)
    data = state(doc)
    if not evidence:
        doc.gateway_settlement_error = ""
        cashfree.save(doc)
        return {"status": "Awaiting bank settlement"}
    if data.get("settlement"):
        old = data["settlement"]
        if old["evidence"] != evidence:
            reject("Settlement details changed after posting; review the existing journal")
        submitted("Journal Entry", old["journal_entry"])
        return old
    shop = frappe.get_doc("LC Shop", doc.shop)
    # Separate real bank from clearing; no transfer into the same ledger.
    bank = shop.get("cashfree_bank_account")
    if not bank or bank == snap["clearing_account"]:
        reject("Configure a separate receiving bank account in Cashfree settings")
    submitted("Payment Entry", doc.payment_entry)
    submitted("Sales Invoice", doc.sales_invoice)
    company = frappe.db.get_value("Sales Invoice", doc.sales_invoice, "company")
    if not company or company != shop.company:
        reject("Original payment Company no longer matches this shop")
    account(bank, company, "Asset", bank=True)
    account(snap["clearing_account"], company, "Asset", bank=True)
    manual = frappe.db.sql(
        """select name from `tabJournal Entry`
        where company=%s and cheque_no=%s and docstatus=1
          and coalesce(user_remark,'') not like 'Cashfree settlement allocation for %%'
        limit 1""",
        (company, evidence["utr"]),
    )
    if manual:
        reject(
            "A bank journal already uses this UTR. Review the existing settlement before posting"
        )
    lines = []
    for amount, name, root in [
        (evidence["net"], bank, "Asset"),
        (evidence["fee"], shop.get("cashfree_fee_account"), "Expense"),
        (evidence["tax"], shop.get("cashfree_fee_tax_account"), "Expense"),
    ]:
        if money(amount):
            account(name, company, root)
            lines.append(
                {
                    "account": name,
                    "debit_in_account_currency": float(amount),
                    "cost_center": shop.cost_center,
                }
            )
    lines.append(
        {
            "account": snap["clearing_account"],
            "credit_in_account_currency": float(evidence["gross"]),
        }
    )
    with posting():
        journal = frappe.get_doc(
            dict(
                doctype="Journal Entry",
                voucher_type="Bank Entry",
                company=company,
                posting_date=frappe.utils.nowdate(),
                cheque_no=evidence["utr"],
                cheque_date=str(evidence["date"])[:10],
                user_remark="Cashfree settlement allocation for " + doc.name,
                accounts=lines,
            )
        ).insert(ignore_permissions=True)
        journal.submit()
        data["settlement"] = {"evidence": evidence, "journal_entry": journal.name}
        doc.gateway_settlement_error = ""
        persist(doc, data)
    return data["settlement"]


def link_refund_credit(order, refund_id, credit_note):
    require_platform()
    from . import cashfree

    cashfree.begin_operation(order)
    doc = cashfree.locked(order)
    data = state(doc)
    if refund_id in data.get("refunds", {}):
        reject("This refund already has accounting entries")
    credit = frappe.get_doc("Sales Invoice", credit_note)
    if credit.docstatus != 1 or not credit.is_return or credit.return_against != doc.sales_invoice:
        reject("Select a submitted credit note against this order invoice")
    data.setdefault("refund_credit_notes", {})[str(refund_id)] = credit.name
    persist(doc, data)
    return {"saved": True}


def prepare_credit(order):
    """Admin edits native item/tax allocations rather than guessing from a cash amount."""
    require_platform()
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

    from . import cashfree

    cashfree.begin_operation(order)
    doc = cashfree.locked(order)
    submitted("Sales Invoice", doc.sales_invoice)
    existing = frappe.db.get_value(
        "Sales Invoice", {"return_against": doc.sales_invoice, "docstatus": 0}, "name"
    )
    if existing:
        return {"credit_note": existing}
    with posting():
        credit = make_sales_return(doc.sales_invoice)
        credit.update_stock = 0
        credit.update_outstanding_for_self = 1
        credit.lc_order = None  # Native admin-editable draft, linked through return_against.
        credit.insert(ignore_permissions=True)
    return {"credit_note": credit.name}


def reconcile_due():
    """Rotate through paid orders, including delivered ones; errors do not starve older orders."""
    from . import cashfree

    shops = frappe.get_all("LC Shop", filters={"cashfree_auto_reconcile": 1}, pluck="name")
    if not shops:
        return
    names = frappe.get_all(
        "LC Order",
        filters={
            "payment_method": "Cashfree",
            "shop": ["in", shops],
            "payment_status": ["in", ["Paid", "Refunded"]],
        },
        pluck="name",
        order_by="gateway_reconciled_at asc, creation asc",
        limit_page_length=20,
    )
    for name in names:
        try:
            shop = frappe.db.get_value("LC Order", name, "shop")
            if not frappe.db.get_value("LC Shop", shop, "cashfree_auto_reconcile"):
                continue
            cashfree.sync(name, authorize=False)
            frappe.db.commit()
            reconcile_settlement(name)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            # Provider errors are already safely logged; never store raw responses/customer data.
            frappe.db.set_value(
                "LC Order",
                name,
                "gateway_settlement_error",
                "Reconciliation needs review. Open Cashfree accounting and retry.",
                update_modified=False,
            )
        finally:
            frappe.db.set_value(
                "LC Order",
                name,
                "gateway_reconciled_at",
                frappe.utils.now_datetime(),
                update_modified=False,
            )
            frappe.db.commit()
