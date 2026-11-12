"""Versioned marketplace cancellations, immutable paise ledger and durable provider intents.

Never infer a bank refund/settlement from acceptance of an HTTP request.
"""
import hashlib
import json
from contextvars import ContextVar
from urllib.parse import quote

import frappe
from local_commerce.permissions.scope import identity, memberships, require_platform
from local_commerce.permissions.policy import is_platform
from local_commerce.services.owner import reject
from local_commerce.services.payments import cashfree
from local_commerce.services import cancellation_policy as policy

writing = ContextVar('marketplace_writing', default=False)
internal_cancel = ContextVar('marketplace_cancel', default=False)


def state(doc):
    return json.loads(doc.get('cancellation_json') or '{}')


def enabled(doc):
    return bool(doc.get('cancellation_policy_json'))


def event(doc, key, kind, data):
    if 'debit' in data or 'credit' in data:
        values = list(data.get('debit', {}).values()) + list(data.get('credit', {}).values())
        if any(type(v) is not int or v < 0 for v in values) or sum(data.get('debit', {}).values()) != sum(data.get('credit', {}).values()):
            reject('Unbalanced marketplace ledger entry')
    key = doc.name + ':' + key
    existing = frappe.db.get_value('LC Marketplace Event', {'event_key': key}, 'data_json')
    if existing:
        if json.loads(existing) != data:
            reject('Previously recorded ledger evidence changed; reconcile before continuing')
        return
    token = writing.set(True)
    try:
        frappe.get_doc(dict(doctype='LC Marketplace Event', order=doc.name, event_key=key,
            event_type=kind, actor=frappe.session.user, data_json=json.dumps(data))).insert(ignore_permissions=True)
    finally:
        writing.reset(token)


def save(doc, case, status):
    case['status'] = status
    doc.cancellation_state = status
    doc.cancellation_json = json.dumps(case)
    cashfree.save(doc)


def owner(doc):
    user, roles = identity()
    return 'LC Shop Owner' in roles and any(m.shop == doc.shop and m.membership_role == 'Owner' for m in memberships(user))


def access(doc):
    user, roles = identity()
    if is_platform(user, roles):
        return 'Admin'
    if owner(doc):
        return 'Shop'
    if user != 'Guest' and user == doc.customer_user:
        return 'Customer'
    frappe.throw('Order cancellation access denied', frappe.PermissionError)


def guard(doc):
    if enabled(doc) and state(doc).get('status') == 'Awaiting approvals' and not internal_cancel.get():
        reject('Resolve the cancellation request before continuing fulfilment')


def snapshot(order, shop, so):
    config = frappe.get_doc('LC Payment Gateway', shop.cashfree_gateway)
    if not config.get('marketplace_policy_enabled'):
        return
    if not config.get('marketplace_hold_confirmed'):
        reject('Confirm Cashfree split-after-payment configuration before enabling marketplace orders')
    if cashfree.settlement_mode(shop) != 'Easy Split':
        reject('Marketplace cancellation policy requires Easy Split')
    # Preserve explicit GST basis and tax treatment; enforce the agreed rate.
    rate = shop.gst_commission_rate if shop.get('gst_enabled') else shop.cashfree_commission
    if str(rate) not in ('7', '7.0', '7.00') or (not shop.get('gst_enabled') and shop.cashfree_commission_type != 'Percentage'):
        reject('Set this shop commission to 7% before enabling marketplace orders')
    order.cancellation_policy_json = json.dumps(dict(version=1, commission_bps=700,
        customer_refund_bps=8500, fee_includes_tax=True, hold='Split after delivery',
        gateway_profile=shop.cashfree_gateway, vendor_id=shop.cashfree_vendor_id,
        total_paise=policy.paise(so.grand_total)))
    order.marketplace_settlement_state = 'Held — no vendor split'


def public(doc):
    if not enabled(doc):
        return None
    case = state(doc)
    result = {k: case[k] for k in ('status','reason','kind','shop_approval','admin_approval','amounts','error','refund_status') if k in case}
    result.update(enabled=True, settlement=doc.get('marketplace_settlement_state'), role=access(doc) if
                  (doc.customer_user == frappe.session.user or owner(doc) or is_platform(*identity())) else 'Viewer')
    return result


def initiate(order, reason):
    from local_commerce.services import orders, returns
    doc = frappe.get_doc('LC Order', order)
    role = access(doc)
    reason = returns.note(reason)
    if not enabled(doc):
        reject('This order uses the original cancellation workflow')
    previous = state(doc)
    if previous and (role == 'Customer' or previous.get('status') not in ('Awaiting approvals','Rejected')):
        return orders.serialize(doc)
    # Provider identity verification occurs before inventory locks.
    evidence = cashfree.prepare_cancellation(doc)
    doc = cashfree.locked(order)
    cashfree.ensure_cancellable(doc, evidence)
    role = access(doc)
    previous_case = state(doc)
    if previous_case and (role == 'Customer' or previous_case.get('status') not in ('Awaiting approvals','Rejected')):
        return orders.serialize(doc)
    if frappe.db.exists('LC Marketplace Operation', {'order':order,'kind':'Delivery split','status':['in',['Queued','Unconfirmed']]}):
        reject('Reconcile the pending delivery split before cancelling this order')
    if returns.state(doc) or doc.get('gateway_refunded_amount'):
        reject('An existing refund/return must be reconciled before cancellation')
    if role == 'Customer' and doc.status not in policy.BEFORE_PREPARING | policy.AFTER_PREPARING:
        reject('This order can no longer be cancelled by the customer')
    if doc.status == 'Cancelled':
        return orders.serialize(doc)
    paid = policy.paise(evidence['case']['paid_amount']) if isinstance(evidence, dict) else 0
    if isinstance(evidence, dict) and policy.paise(evidence['case']['amount']) != paid:
        reject('Previous refunds require administrator reconciliation')
    late = role == 'Customer' and doc.status in policy.AFTER_PREPARING
    case = dict(reason=reason, requested_by=frappe.session.user, requested_at=str(frappe.utils.now_datetime()),
        original_status=doc.status, paid_paise=paid, payment_id=evidence['payment_id'] if isinstance(evidence, dict) else None,
        kind='Approved customer request' if late else 'Customer before preparing' if role == 'Customer' else 'Shop cancellation')
    if paid:
        event(doc, 'payment', 'Payment verified', {'payment_id':case['payment_id'],
            'debit':{'cashfree_receivable':paid}, 'credit':{'order_funds':paid}})
    event(doc, 'owner-override' if previous_case else 'requested', 'Cancellation requested', case)
    save(doc, case, 'Awaiting approvals' if late else 'Awaiting fee evidence')
    if not late:
        cancel(doc, case)
    return orders.detail(order)


def cancel(doc, case):
    from local_commerce.services import orders
    token = internal_cancel.set(True)
    try:
        orders.change(doc.name, 'Cancelled', case['reason'][:500])
    finally:
        internal_cancel.reset(token)
    doc.reload()
    doc.commission_pending = 0
    doc.marketplace_settlement_state = 'Cancellation hold — refund pending' if case['paid_paise'] else 'No settlement — unpaid cancellation'
    if case.get('payment_id'):
        doc.gateway_payment_id = case['payment_id']
    save(doc, case, 'Awaiting fee evidence' if case['paid_paise'] else 'Completed — no payment')
    event(doc, 'cancelled', 'Order cancelled', {'kind':case['kind'], 'paid_paise':case['paid_paise']})
    if case['paid_paise']:
        frappe.enqueue('local_commerce.services.marketplace.process', order=doc.name, enqueue_after_commit=True)


def approve(order, decision, note, role):
    from local_commerce.services import returns, orders
    doc = frappe.get_doc('LC Order', order)
    if role == 'Admin':
        require_platform()
    elif role != 'Shop' or not owner(doc):
        frappe.throw('Shop owner approval required', frappe.PermissionError)
    note = returns.note(note)
    if decision not in ('Approve', 'Reject'):
        reject('Choose approve or reject')
    cashfree.begin_operation(order)
    doc = cashfree.locked(order)
    case = state(doc)
    if case.get('status') != 'Awaiting approvals':
        reject('This request is no longer awaiting approval')
    field = role.lower() + '_approval'
    other = case.get('admin_approval' if role == 'Shop' else 'shop_approval') or {}
    if other.get('by') == frappe.session.user:
        reject('Shop owner and administrator approvals must come from different people')
    if case.get(field):
        return orders.serialize(doc)
    case[field] = dict(by=frappe.session.user, decision=decision, note=note, at=str(frappe.utils.now_datetime()))
    event(doc, field, role + ' decision', case[field])
    if decision == 'Reject':
        save(doc, case, 'Rejected')
    elif case.get('shop_approval', {}).get('decision') == case.get('admin_approval', {}).get('decision') == 'Approve':
        save(doc, case, 'Approved')
        cancel(doc, case)
    else:
        save(doc, case, 'Awaiting approvals')
    return orders.detail(order)


def recon(doc):
    return cashfree.request(doc.gateway_profile, 'POST', '/split/order/vendor/recon',
        {'filters': {'order_ids': [doc.gateway_order_id]}}, api_version='2026-01-01')


def operation(doc, kind, payload):
    key = doc.name + ':' + kind
    name = frappe.db.get_value('LC Marketplace Operation', {'operation_key':key}, 'name')
    if name:
        op = frappe.get_doc('LC Marketplace Operation', name, for_update=True)
        if json.loads(op.payload_json) != payload:
            reject('A persisted financial instruction cannot change')
        return op
    token = writing.set(True)
    try:
        return frappe.get_doc(dict(doctype='LC Marketplace Operation', order=doc.name, operation_key=key,
            kind=kind, status='Queued', payload_json=json.dumps(payload))).insert(ignore_permissions=True)
    finally:
        writing.reset(token)


def op_save(op, status, response=None):
    token = writing.set(True)
    try:
        op.status = status
        if response is not None:
            op.response_json = json.dumps(response)
        op.save(ignore_permissions=True)
    finally:
        writing.reset(token)


def send(doc, op, path):
    if op.status in ('Accepted','Confirmed'):
        return True
    if op.status == 'Unconfirmed':
        reject('Provider request is unconfirmed. Reconcile before any further money movement.')
    op_save(op, 'Unconfirmed')
    event(doc, op.kind + ':intent', 'Provider instruction', {'operation':op.name,'kind':op.kind,'payload':json.loads(op.payload_json)})
    frappe.db.commit()  # Intent is durable even if the network response is lost.
    result = cashfree.request(doc.gateway_profile, 'POST', path, json.loads(op.payload_json),
        key=op.operation_key, api_version='2026-01-01')
    if op.kind == 'Delivery split' and result.get('status') != 'OK':
        reject('Cashfree has not confirmed the split')
    if op.kind in ('Compensation', 'Cancellation cost'):
        details = result.get('transfer_details') or {}
        expected = json.loads(op.payload_json)
        if (not result.get('settlement_id') or details.get('vendor_id') != json.loads(doc.cancellation_policy_json)['vendor_id']
                or any(details.get(k) != expected[k] for k in ('transfer_from','transfer_type'))
                or policy.paise(details.get('transfer_amount')) != policy.paise(expected['transfer_amount'])):
            reject('Cashfree transfer response does not match the instruction')
    # Acquire locks again: commit released the payment mutex.
    cashfree.begin_operation(doc.name)
    doc = cashfree.locked(doc.name)
    op = frappe.get_doc('LC Marketplace Operation', op.name, for_update=True)
    op_save(op, 'Accepted', result)
    event(doc, op.kind + ':accepted', 'Provider accepted', {'operation':op.name,'response':result})
    if op.kind == 'Delivery split':
        value = policy.paise(json.loads(op.payload_json)['split'][0]['amount'])
        event(doc, 'delivery:split', 'Vendor split accepted', {'debit':{'vendor_payable':value},'credit':{'cashfree_receivable':value}})
    if op.kind in ('Compensation','Cancellation cost'):
        value = policy.paise(json.loads(op.payload_json)['transfer_amount'])
        debit, credit = ({'vendor_payable':value}, {'cashfree_receivable':value}) if op.kind == 'Compensation' else ({'cashfree_receivable':value}, {'shop_receivable':value})
        event(doc, op.kind + ':ledger', 'Vendor balance adjustment', {'debit':debit,'credit':credit,'provider_reference':result['settlement_id']})
    return True


def queue_refund(doc, case):
    from local_commerce.services.return_rules import refund_evidence
    amount = case['amounts']['refund_paise']
    if not amount:
        return True
    rid = 'mp_' + hashlib.sha256(doc.name.encode()).hexdigest()[:28]
    path = '/orders/' + quote(doc.gateway_order_id, safe='') + '/refunds'
    payload = dict(refund_id=rid, refund_amount=float(policy.rupees(amount)), refund_speed='STANDARD',
                   refund_note='Marketplace cancellation ' + doc.name)
    if case.get('vendor_refund_paise'):
        payload['refund_splits'] = [dict(vendor_id=json.loads(doc.cancellation_policy_json)['vendor_id'],
            amount=float(policy.rupees(case['vendor_refund_paise'])))]
    op = operation(doc, 'Refund', payload)
    rows = cashfree.request(doc.gateway_profile, 'GET', path)
    snap = dict(order_id=doc.gateway_order_id, currency='INR', amount=policy.rupees(case['paid_paise']))
    row = refund_evidence(rows, snap, case['payment_id'], rid, policy.rupees(amount))
    if row:
        if row['refund_status'] == 'SUCCESS':
            op_save(op, 'Confirmed', row)
            event(doc, 'refund:confirmed', 'Customer refund confirmed', {'refund_paise':amount,'provider_id':row['cf_refund_id'],
                'debit':{'customer_refund':amount},'credit':{'cashfree_receivable':amount}})
            if case.get('vendor_refund_paise'):
                vendor = case['vendor_refund_paise']
                event(doc, 'vendor-refund-reversal', 'Original vendor allocation recovered in refund',
                    {'debit':{'cashfree_receivable':vendor},'credit':{'vendor_payable':vendor}})
            case['refund_status'] = 'Cashfree confirmed refund success'
            doc.gateway_refunded_amount = float(policy.rupees(amount))
            doc.payment_status = 'Refunded' if amount == case['paid_paise'] else 'Paid'
            cashfree.save(doc)
            return True
        if row['refund_status'] in ('FAILED','CANCELLED'):
            reject('Cashfree refund failed. Review the existing refund; do not create a duplicate.')
        return False
    # Refund IDs are provider-unique; an uncertain retry always reuses the same ID/key/payload.
    if op.status == 'Unconfirmed':
        op_save(op, 'Queued')
    send(doc, op, path)
    return False


def process(order):
    """Worker: recoverable actions use stable identities; transfers never retry uncertain POSTs."""
    acquired = False
    try:
        cashfree.begin_operation(order)
        acquired = True
        doc = cashfree.locked(order)
        if not enabled(doc):
            return
        case = state(doc)
        if not case or case.get('status') == 'Rejected':
            release_delivery(doc)
            frappe.db.commit()
            return
        if doc.status != 'Cancelled' or case.get('status') in ('Completed','Completed — no payment','Rejected','Awaiting approvals'):
            return
        if not case.get('amounts'):
            data = recon(doc)
            fees = policy.fee_evidence(data, doc.gateway_order_id, case['payment_id'], case['paid_paise'])
            # Any prior vendor split must be resolved explicitly, never blindly refunded.
            vendors = [r for r in data['data'] if r.get('entity_type') == 'vendor_commission']
            known = frappe.db.exists('LC Marketplace Operation', {'order':doc.name,'kind':'Delivery split','status':['in',['Accepted','Confirmed']]})
            if known and not vendors:
                reject('Wait for Cashfree to report the accepted split before refunding')
            if vendors:
                snap = json.loads(doc.gateway_snapshot)
                if (case['kind'] != 'Shop cancellation' or not known or len(vendors) != 1
                        or vendors[0].get('merchant_vendor_id') != snap['vendor_id']
                        or vendors[0].get('merchant_order_id') != doc.gateway_order_id
                        or vendors[0].get('currency') != 'INR'
                        or policy.paise(vendors[0]['amount']) != policy.paise(snap['vendor_amount'])
                        or policy.paise(vendors[0]['amount']) > case['paid_paise']):
                    reject('Unexpected vendor split; administrator reconciliation is required')
                case['vendor_refund_paise'] = policy.paise(snap['vendor_amount'])
            case['fee_evidence'] = fees
            case['amounts'] = policy.allocation(case['paid_paise'], fees['total_paise'], case['kind'])
            a = case['amounts']
            original = frappe.db.get_value('LC Marketplace Event', {'event_key':doc.name + ':delivery:allocation'}, 'data_json')
            if original:
                original = json.loads(original)
                event(doc, 'delivery:reversed', 'Delivery allocation reversed for cancellation',
                    {'debit':original['credit'],'credit':original['debit']})
            event(doc, 'allocation', 'Cancellation allocation', dict(amounts=a, fee_evidence=fees,
                debit={'order_funds':a['paid_paise'],'shop_receivable':a['shop_debt_paise']},
                credit={'customer_refund':a['refund_paise'],'vendor_payable':a['vendor_paise'],'gateway_cost':a['gateway_fee_paise']}))
            event(doc, 'gateway-fee', 'Verified gateway charges allocated',
                {'debit':{'gateway_cost':a['gateway_fee_paise']},'credit':{'cashfree_receivable':a['gateway_fee_paise']}})
            case.pop('error', None)
            save(doc, case, 'Refund pending')
            frappe.db.commit()
            cashfree.begin_operation(order)
            doc = cashfree.locked(order)
        if not queue_refund(doc, case):
            save(doc, case, 'Refund pending')
            frappe.db.commit()
            return
        doc.reload()
        save(doc, case, 'Refund confirmed — allocating shop amounts')
        a = case['amounts']
        if a['vendor_paise']:
            op = operation(doc, 'Compensation', dict(transfer_from='MERCHANT',transfer_type='ADJUSTMENT',
                transfer_amount=float(policy.rupees(a['vendor_paise'])),remark='Preparation compensation '+doc.name))
            send(doc, op, '/easy-split/vendors/' + quote(json.loads(doc.cancellation_policy_json)['vendor_id'], safe='') + '/transfer')
        if a['shop_debt_paise']:
            op = operation(doc, 'Cancellation cost', dict(transfer_from='VENDOR',transfer_type='ADJUSTMENT',
                transfer_amount=float(policy.rupees(a['shop_debt_paise'])),remark='Cancellation gateway cost '+doc.name))
            send(doc, op, '/easy-split/vendors/' + quote(json.loads(doc.cancellation_policy_json)['vendor_id'], safe='') + '/transfer')
        doc.reload()
        doc.marketplace_settlement_state = 'Cancellation allocated — check vendor settlement'
        case.pop('error', None)
        doc.gateway_accounting_error = 'Marketplace cancellation ledger recorded. Link the cancellation credit note and reconcile commission reversal in Cashfree accounting.'
        save(doc, case, 'Completed')
        event(doc, 'completed', 'Cancellation financial instructions completed', a)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        if not acquired:
            return
        frappe.log_error(title='Marketplace cancellation/settlement review', message=frappe.get_traceback())
        doc = cashfree.locked(order)
        case = state(doc)
        if case and case.get('status') not in ('Awaiting approvals','Rejected','Completed','Completed — no payment'):
            case['error'] = 'Waiting for verified fees or provider reconciliation. Administrator: check financial activity.'
            save(doc, case, 'Needs review' if case.get('amounts') else 'Awaiting fee evidence')
        elif not case or case.get('status') == 'Rejected':
            doc.marketplace_settlement_state = 'Needs review — settlement not confirmed'
            cashfree.save(doc)
        frappe.db.commit()


def release_delivery(doc):
    if doc.status != 'Delivered' or not doc.delivered_at or doc.payment_status != 'Paid':
        return
    if state(doc) and state(doc).get('status') != 'Rejected':
        return
    if doc.gateway_accounting_error or doc.gateway_refunded_amount:
        reject('Resolve payment accounting before releasing a vendor split')
    # Cashfree requires two minutes after payment confirmation; delivery time is a conservative anchor.
    if frappe.utils.time_diff_in_seconds(frappe.utils.now_datetime(), doc.delivered_at) < 120:
        return
    snap = json.loads(doc.gateway_snapshot)
    amount = policy.paise(snap['vendor_amount'])
    total = policy.paise(snap['amount'])
    tax = (snap.get('gst') or {}).get('amounts')
    distribution = {'vendor_payable':amount, 'platform_commission':total - amount}
    if tax:
        distribution = {'vendor_payable':amount,'platform_commission':policy.paise(tax['commission_base']),
            'commission_gst':policy.paise(tax['commission_tax']),'supply_gst':policy.paise(tax['eco_tax'])}
    payment = json.loads(doc.get('gateway_accounting_json') or '{}').get('payment_evidence') or {}
    discount = policy.paise(payment.get('discount_amount', 0))
    if discount:
        event(doc, 'offer-funding', 'Verified offer receivable', {'debit':{'offer_receivable':discount},'credit':{'order_funds':discount}})
    event(doc, 'delivery:allocation', 'Delivery allocation', {'debit':{'order_funds':total},'credit':distribution})
    op = operation(doc, 'Delivery split', dict(split=[dict(vendor_id=snap['vendor_id'], amount=float(policy.rupees(amount)))], disable_split=True))
    if op.status in ('Accepted', 'Confirmed'):
        check_delivery_settlement(doc)
        return
    # Verify there are no dashboard-created or automatic splits before releasing funds.
    data = recon(doc)
    if not isinstance(data, dict) or data.get('cursor') or not isinstance(data.get('data'), list):
        reject('Complete split reconciliation is required before releasing funds')
    vendors = [r for r in data['data'] if r.get('entity_type') == 'vendor_commission']
    if vendors:
        prior_intent = frappe.db.exists('LC Marketplace Event', {'event_key':doc.name + ':Delivery split:intent'})
        if (not prior_intent or len(vendors) != 1 or vendors[0].get('merchant_order_id') != doc.gateway_order_id
                or vendors[0].get('merchant_vendor_id') != snap['vendor_id'] or vendors[0].get('currency') != 'INR'
                or policy.paise(vendors[0]['amount']) != amount):
            reject('Reconcile existing provider splits before releasing funds')
        op_save(op, 'Accepted', {'reconciled': True, 'vendor_amount_paise':amount})
        event(doc, 'delivery:split', 'Vendor split accepted', {'debit':{'vendor_payable':amount},'credit':{'cashfree_receivable':amount}})
        event(doc, 'split-recovered', 'Existing vendor split verified without resending', {'vendor_amount_paise':amount})
        doc.marketplace_settlement_state = 'Split accepted — awaiting bank settlement'
        cashfree.save(doc)
        check_delivery_settlement(doc)
        return
    send(doc, op, '/easy-split/orders/' + quote(doc.gateway_order_id, safe='') + '/split')
    doc.reload()
    doc.marketplace_settlement_state = 'Split accepted — awaiting bank settlement'
    cashfree.save(doc)


def pending():
    names = frappe.get_all('LC Order', filters={'cancellation_state':['in',['Awaiting fee evidence','Refund pending','Refund confirmed — allocating shop amounts']]}, pluck='name', order_by='modified asc', limit_page_length=30)
    delivered = frappe.get_all('LC Order', filters={'status':'Delivered','marketplace_settlement_state':['in',['Held — no vendor split','Split accepted — awaiting bank settlement']]}, pluck='name', order_by='modified asc', limit_page_length=30)
    for name in dict.fromkeys(names + delivered):
        process(name)


def retry(order):
    require_platform()
    doc = cashfree.locked(order)
    if not enabled(doc):
        reject('Not a marketplace policy order')
    frappe.enqueue('local_commerce.services.marketplace.process', order=order, enqueue_after_commit=True)
    return {'queued':True}


def payment_verified(doc, paid, payment_id):
    if enabled(doc):
        amount = policy.paise(paid)
        event(doc, 'payment', 'Payment verified', {'payment_id':payment_id,
            'debit':{'cashfree_receivable':amount}, 'credit':{'order_funds':amount}})


def check_delivery_settlement(doc):
    data = recon(doc)
    from local_commerce.services.payments.reconciliation_rules import settlement_evidence
    snap = json.loads(doc.gateway_snapshot)
    evidence = settlement_evidence(data, snap, doc.gateway_order_id, doc.gateway_payment_id)
    if not evidence:
        cashfree.save(doc)  # Rotate pending settlements through the bounded recovery batch.
    if evidence:
        if doc.status != 'Delivered' or not frappe.db.exists('LC Marketplace Operation', {'order':doc.name,'kind':'Delivery split','status':['in',['Accepted','Confirmed']]}):
            reject('Cashfree shows a vendor settlement without an authorized delivery split. Review the provider configuration.')
        doc.marketplace_settlement_state = 'Vendor bank settlement confirmed'
        cashfree.save(doc)
        event(doc, 'settled:' + evidence['reference'], 'Vendor bank settlement confirmed', evidence)
    return evidence


def settlement_check(order):
    require_platform()
    cashfree.begin_operation(order)
    doc = cashfree.locked(order)
    if not enabled(doc):
        reject('Not a marketplace policy order')
    if doc.status != 'Cancelled':
        evidence = check_delivery_settlement(doc)
        return dict(status=doc.marketplace_settlement_state, evidence=evidence)
    confirmed = []
    vendor = json.loads(doc.cancellation_policy_json)['vendor_id']
    names = frappe.get_all('LC Marketplace Operation', filters={'order':order,
        'kind':['in',['Compensation','Cancellation cost']], 'status':['in',['Accepted','Confirmed']]}, pluck='name')
    for name in names:
        op = frappe.get_doc('LC Marketplace Operation', name, for_update=True)
        response = json.loads(op.response_json or '{}')
        sid = response.get('settlement_id')
        if not sid:
            continue
        data = cashfree.request(doc.gateway_profile, 'POST', '/recon/vendor',
            {'pagination':{'limit':100,'cursor':None}, 'filters':{'settlement_id':sid}}, api_version='2026-01-01')
        if data.get('cursor'):
            reject('Settlement history is paginated; review the full provider report')
        rows = [r for r in data.get('data',[]) if str(r.get('settlement_id')) == str(sid)
                and r.get('merchant_vendor_id') == vendor and r.get('type') == 'vendor_settlement']
        if len(rows) == 1 and rows[0].get('settled') is True and rows[0].get('currency') == 'INR' and rows[0].get('settlement_utr') not in (None,'','NA','N/A'):
            row = rows[0]
            event(doc, 'transfer-settled:' + op.name, 'Vendor adjustment bank settlement confirmed',
                {'operation':op.name,'settlement_id':sid,'utr':row['settlement_utr']})
            op_save(op, 'Confirmed', response)
            confirmed.append(op.name)
    return dict(status=doc.marketplace_settlement_state, confirmed_operations=confirmed)


def retry_operation(order, operation_name):
    require_platform()
    cashfree.begin_operation(order)
    doc = cashfree.locked(order)
    op = frappe.get_doc('LC Marketplace Operation', operation_name, for_update=True)
    if op.order != order or op.status != 'Unconfirmed':
        reject('Select an unconfirmed operation belonging to this order')
    if not enabled(doc):
        reject('This order does not use the marketplace policy')
    if op.kind == 'Delivery split' and (doc.status != 'Delivered' or (state(doc) and state(doc).get('status') != 'Rejected')):
        reject('A cancelled or disputed order cannot release a delivery split')
    if op.kind != 'Delivery split' and doc.status != 'Cancelled':
        reject('Cancellation instructions require a cancelled order')
    # Cashfree documents idempotency for these endpoints. Only an explicit admin
    # retry may resend an uncertain transfer, using the persisted key and payload.
    op_save(op, 'Queued')
    event(doc, 'retry:' + op.name + ':' + frappe.generate_hash(length=12), 'Administrator requested same-operation retry',
          {'operation':op.name,'idempotency_key':op.operation_key})
    frappe.enqueue('local_commerce.services.marketplace.process', order=order, enqueue_after_commit=True)
    return {'queued':True}
