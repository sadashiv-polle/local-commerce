"""One auditable return case per delivered order; durable, admin-approved refunds."""
import json
from urllib.parse import quote
import frappe
from local_commerce.permissions.scope import require_platform, require_shop
from local_commerce.services.owner import reject
from local_commerce.services.payments import cashfree
from local_commerce.services.payments.rules import money
from local_commerce.services.return_rules import approved_amount, refund_evidence, refund_payload


def state(doc):
    return json.loads(doc.get('return_request_json') or '{}')


def public(doc):
    case = state(doc)
    return {k: case[k] for k in ('status','reason','review_note','decision_note','kind','amount',
        'requested_at','reviewed_at','approved_at','updated_at','events','stock_note') if k in case}


def lock(order):
    doc = frappe.get_doc('LC Order', order)
    frappe.db.sql('select name from `tabLC Shop` where name=%s for update', (doc.shop,))
    return frappe.get_doc('LC Order', order, for_update=True)


def save(doc, case, status):
    case['status'] = status
    case['updated_at'] = str(frappe.utils.now_datetime())
    case.setdefault('events', []).append(dict(status=status, at=case['updated_at']))
    doc.return_request_json = json.dumps(case)
    doc.return_status = status
    cashfree.save(doc)


def note(value):
    value = str(value or '').strip()
    if not 3 <= len(value) <= 1000:
        reject('Enter a reason between 3 and 1000 characters')
    return value


def request_return(order, reason):
    doc = frappe.get_doc('LC Order', order)
    if frappe.session.user == 'Guest' or doc.customer_user != frappe.session.user:
        frappe.throw('Only the order customer can request a return', frappe.PermissionError)
    reason = note(reason)
    doc = lock(order)
    if doc.status != 'Delivered':
        reject('Returns are available after delivery. Contact the shop for cancellation before delivery.')
    if state(doc):
        return public(doc)
    case = dict(reason=reason, requested_at=str(frappe.utils.now_datetime()),
        requested_by=frappe.session.user, stock_note='Not returned to sellable stock')
    save(doc, case, 'Requested')
    return public(doc)


def review(order, review_note):
    doc = frappe.get_doc('LC Order', order)
    require_shop(doc.shop, 'write')
    doc = lock(order)
    case = state(doc)
    if case.get('status') != 'Requested':
        reject('This return has already been reviewed. Refresh the order.')
    case.update(review_note=note(review_note), reviewed_by=frappe.session.user,
        reviewed_at=str(frappe.utils.now_datetime()))
    save(doc, case, 'Reviewed')
    return public(doc)


def decide(order, decision, decision_note, kind='Full', amount=None, credit_note=None):
    require_platform()
    doc = lock(order)
    case = state(doc)
    if case.get('status') not in ('Requested', 'Reviewed'):
        reject('This return is already decided. Refresh to see its current status.')
    case.update(decision_note=note(decision_note), approved_by=frappe.session.user,
        approved_at=str(frappe.utils.now_datetime()))
    if decision == 'Reject':
        save(doc, case, 'Rejected')
        return public(doc)
    if decision != 'Approve':
        reject('Choose approve or reject')
    if doc.payment_method != 'Cashfree':
        reject('COD and Manual UPI refunds need manual payment and accounting handling. Contact the administrator; no money has been sent.')
    if doc.status != 'Delivered' or not doc.gateway_payment_id or doc.payment_status != 'Paid':
        reject('A verified paid, delivered Cashfree order is required')
    snap = json.loads(doc.gateway_snapshot)
    try:
        approved = approved_amount(kind, amount, snap['amount'], doc.gateway_refunded_amount)
    except (ValueError, ArithmeticError) as exc:
        reject(str(exc))
    case.update(kind=kind, amount=str(approved), refund_id='ret_' + frappe.generate_hash(length=28))
    case['payload'] = refund_payload(case, snap)
    if doc.get('gst_snapshot'):
        from local_commerce.services.gst.accounting import refund_allocation
        gst = json.loads(doc.gst_snapshot)
        if approved != money(snap['amount']):
            if not credit_note:
                reject('Select the submitted item-specific credit note before approving a partial GST refund')
            credit = frappe.get_doc('Sales Invoice', credit_note)
            original = frappe.get_doc('Sales Invoice', doc.sales_invoice)
            if (credit.docstatus != 1 or not credit.is_return or credit.return_against != original.name
                    or credit.company != original.company or credit.customer != original.customer
                    or credit.currency != 'INR' or not credit.update_outstanding_for_self
                    or credit.grand_total >= 0 or money(abs(credit.grand_total)) != approved
                    or credit.outstanding_amount >= 0 or money(abs(credit.outstanding_amount)) != approved):
                reject('Select an unpaid submitted credit note matching this order and approved refund amount')
            parts = refund_allocation(doc, credit)
            case['credit_note'] = credit.name
        else:
            parts = gst['amounts']
        if money(parts['total']) != approved:
            reject('Credit note components do not match the approved refund')
        case['payload']['refund_splits'] = [dict(vendor_id=snap['vendor_id'], amount=float(money(parts['vendor_amount'])))]

    save(doc, case, 'Refund queued')
    frappe.enqueue('local_commerce.services.returns.process', order=doc.name, enqueue_after_commit=True)
    return public(doc)


def retry(order):
    require_platform()
    doc = lock(order)
    case = state(doc)
    if case.get('status') not in ('Needs review', 'Refund processing', 'Refund queued'):
        reject('There is no pending refund to check')
    # Reuse approved amount, vendor allocation and stable refund ID after uncertainty.
    save(doc, case, 'Refund queued')
    frappe.enqueue('local_commerce.services.returns.process', order=doc.name, enqueue_after_commit=True)
    return public(doc)


def process(order):
    """Job only: approval already committed before any external money movement."""
    acquired = False
    try:
        cashfree.begin_operation(order)
        acquired = True
        doc = cashfree.payment_order(order)
        case = state(doc)
        if case.get('status') not in ('Refund queued', 'Refund processing'):
            return
        snap = json.loads(doc.gateway_snapshot)
        snap['order_id'] = doc.gateway_order_id
        path = '/orders/' + quote(doc.gateway_order_id, safe='') + '/refunds'
        rows = cashfree.request(doc.gateway_profile, 'GET', path)
        row = refund_evidence(rows, snap, doc.gateway_payment_id, case['refund_id'], case['amount'])
        if row is None:
            # Provider enforces this refund ID / idempotency key even if a worker crashes.
            cashfree.request(doc.gateway_profile, 'POST', path, case['payload'],
                key=doc.gateway_order_id + ':' + case['refund_id'])
            rows = cashfree.request(doc.gateway_profile, 'GET', path)
            row = refund_evidence(rows, snap, doc.gateway_payment_id, case['refund_id'], case['amount'])
        status = (row or {}).get('refund_status')
        doc = cashfree.locked(order)
        case = state(doc)
        if status == 'SUCCESS' and case.get('credit_note'):
            from local_commerce.services.payments.accounting import state as accounting_state, persist
            data = accounting_state(doc)
            data.setdefault('refund_credit_notes', {})[str(row['cf_refund_id'])] = case['credit_note']
            persist(doc, data)
        if status == 'SUCCESS':
            save(doc, case, 'Refund processing')
        elif status in ('FAILED', 'CANCELLED'):
            save(doc, case, 'Needs review')
        else:
            save(doc, case, 'Refund processing')
        frappe.db.commit()
        # Reuse signature-independent server verification and existing credit/refund accounting.
        cashfree.sync(order, authorize=False)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title='Local dot return refund needs review', message=frappe.get_traceback())
        if not acquired:
            return
        doc = lock(order)
        case = state(doc)
        if case.get('status') in ('Refund queued', 'Refund processing'):
            save(doc, case, 'Needs review')
        frappe.db.commit()


def observe(doc, rows):
    """Called only with provider rows already validated by Cashfree sync."""
    case = state(doc)
    if not case.get('refund_id') or case.get('status') == 'Refund completed':
        return
    for row in rows:
        if row.get('refund_id') != case['refund_id']:
            continue
        if money(row['refund_amount']) != money(case['amount']):
            raise ValueError('Return refund amount differs from approval')
        status = row.get('refund_status')
        target = 'Refund completed' if status == 'SUCCESS' else 'Needs review' if status in ('FAILED','CANCELLED') else 'Refund processing'
        if case.get('status') != target:
            save(doc, case, target)
        return


def process_pending():
    # Recovers missed enqueue/webhooks; failed/uncertain cases need an admin retry.
    for name in frappe.get_all('LC Order', filters={'return_status':['in', ['Refund queued','Refund processing']]},
            pluck='name', order_by='modified asc', limit_page_length=20):
        process(name)


def record_manual(order, credit_note, payment_entry, decision_note):
    """Record an already submitted refund; never claim a bank transfer was initiated here."""
    require_platform()
    doc = lock(order)
    case = state(doc)
    if case.get('status') not in ('Requested', 'Reviewed') or doc.payment_method == 'Cashfree':
        reject('Use this action only for an undecided COD or Manual UPI return')
    if doc.payment_method not in ('Cash on Delivery', 'Manual UPI') or not doc.sales_invoice:
        reject('Review the original invoice before recording a manual refund')
    invoice = frappe.get_doc('Sales Invoice', doc.sales_invoice)
    credit = frappe.get_doc('Sales Invoice', credit_note)
    payment = frappe.get_doc('Payment Entry', payment_entry)
    amount = money(abs(credit.grand_total))
    refs = payment.get('references') or []
    if (invoice.docstatus != 1 or credit.docstatus != 1 or not credit.is_return
            or credit.return_against != invoice.name or credit.company != invoice.company
            or credit.customer != invoice.customer or credit.currency != invoice.currency
            or credit.get("update_stock") or credit.grand_total >= 0 or amount > money(invoice.grand_total)
            or amount <= 0 or money(abs(credit.outstanding_amount)) != 0
            or payment.docstatus != 1 or payment.payment_type != 'Pay'
            or payment.company != invoice.company or payment.party_type != 'Customer'
            or payment.party != invoice.customer or payment.paid_from_account_currency != invoice.currency
            or payment.paid_to_account_currency != invoice.currency or money(payment.paid_amount) != amount
            or len(refs) != 1 or refs[0].reference_doctype != 'Sales Invoice'
            or refs[0].reference_name != credit.name or money(abs(refs[0].allocated_amount)) != amount):
        reject('Select a submitted, fully paid return credit note for this order and its matching customer refund Payment Entry')
    if doc.get('gst_snapshot'):
        from local_commerce.services.gst.accounting import reverse_refund
        reverse_refund(doc, credit, dict(cf_refund_id='manual-'+credit.name, refund_amount=float(amount)))
    case.update(amount=str(amount), kind='Full' if amount == money(invoice.grand_total) else 'Partial',
        approved_by=frappe.session.user, approved_at=str(frappe.utils.now_datetime()),
        decision_note=note(decision_note), credit_note=credit.name, payment_entry=payment.name)
    save(doc, case, 'Manual refund recorded')
    return public(doc)
