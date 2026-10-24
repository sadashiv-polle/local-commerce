"""Immutable tax invoices/credit notes backed by balanced native ERPNext journals."""
import json
from contextvars import ContextVar
import frappe
from local_commerce.services.owner import reject
from local_commerce.services.payments.rules import money
from local_commerce.services.payments.accounting import posting, submitted
from .rules import split_tax, refund_parts
from .config import account

writing = ContextVar('lc_gst_writing', default=False)


def line(name, amount, debit=False, cost_center=None):
    return dict(account=name, **{('debit_in_account_currency' if debit else 'credit_in_account_currency'): float(money(amount))}, cost_center=cost_center)


def journal(company, lines, remark, reverse=False, posting_date=None, utr=None):
    if reverse:
        for row in lines:
            debit, credit = row.pop('debit_in_account_currency', 0), row.pop('credit_in_account_currency', 0)
            row.update(debit_in_account_currency=credit, credit_in_account_currency=debit)
    lines = [r for r in lines if r.get('debit_in_account_currency') or r.get('credit_in_account_currency')]
    if not lines:
        return None
    for row in lines:
        ledger = frappe.get_doc('Account', row['account'])
        if ledger.company != company or ledger.disabled or ledger.is_group or ledger.account_currency != 'INR':
            reject('A snapshotted GST ledger is no longer valid')
    doc = frappe.get_doc(dict(doctype='Journal Entry', voucher_type='Journal Entry', company=company,
        posting_date=posting_date or frappe.utils.nowdate(), cheque_no=utr,
        cheque_date=posting_date if utr else None, user_remark=remark, accounts=lines))
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc.name


def existing(key):
    name = frappe.db.get_value('LC GST Document', {'event_key': key}, 'name')
    if not name:
        return None
    doc = frappe.get_doc('LC GST Document', name)
    for field in ('platform_journal','shop_journal'):
        if doc.get(field):
            submitted('Journal Entry', doc.get(field))
    if doc.get('sales_invoice'):
        submitted('Sales Invoice', doc.sales_invoice)
    return doc


def record(order, snapshot, values, kind, platform_journal, shop_journal, refund_id='', original=None, items=None, sales_invoice=None):
    token = writing.set(True)
    try:
        return frappe.get_doc(dict(doctype='LC GST Document', event_key=f'{order.name}:{kind}:{refund_id}',
            order=order.name, shop=order.shop, kind=kind, original=original, refund_id=refund_id,
            posting_date=(frappe.db.get_value('Sales Invoice', sales_invoice, 'posting_date') if sales_invoice else frappe.utils.nowdate()),
            sales_invoice=sales_invoice, delivered_at=order.get('delivered_at'), platform_journal=platform_journal, shop_journal=shop_journal,
            payload=json.dumps(dict(snapshot=snapshot, amounts=values, items=items or [],
                customer=json.loads(order.address_snapshot), recipient=order.recipient, issued_by=frappe.session.user)))).insert(ignore_permissions=True)
    finally:
        writing.reset(token)


def post(order, invoice):
    if not order.get('gst_snapshot'):
        return
    snap = json.loads(order.gst_snapshot)
    if invoice.company != snap['shop_company'] or money(invoice.grand_total) != money(snap['amounts']['total']):
        reject('Invoice differs from the immutable GST checkout snapshot')
    with posting():
        return post_documents(order, snap, snap['amounts'], invoice=invoice)


def post_documents(order, snap, values, refund_id='', invoice=None):
    reverse = bool(refund_id)
    platform, amounts = snap['platform'], values
    pa = platform['accounts']
    suffix = 'Credit Note' if reverse else 'Invoice'
    cashfree = snap['payment_method'] == 'Cashfree'
    holding = pa['clearing'] if cashfree else pa['receivable']
    shop_credit = (json.loads(order.gateway_snapshot)['clearing_account'] if cashfree else snap['shop_payable'])
    results = []
    for role in ('Commission', 'Restaurant'):
        if role == 'Commission' and snap.get('version') == 2:
            from .commission import post as post_commission
            result = post_commission(order, snap, values, refund_id)
            if result:
                results.append(result)
            continue
        if role == 'Restaurant' and snap['mode'] != 'Restaurant 9(5)':
            continue
        kind = role+' '+suffix
        key = f'{order.name}:{kind}:{refund_id}'
        old = existing(key)
        if old:
            if json.loads(old.payload)['amounts'] != values:
                reject('Previously posted GST amounts changed')
            results.append(old)
            continue
        original = None
        if reverse:
            original = existing(f'{order.name}:{role} Invoice:')
            if not original:
                reject('Post the original GST invoice before its refund adjustment')
        if role == 'Commission':
            total, taxable, tax = (amounts[k] for k in ('commission_gross','commission_base','commission_tax'))
            tax_heads = split_tax(tax, platform['party']['state'] != snap['shop_party']['state'])
            platform_lines = [line(holding, total, True), line(pa['income'], taxable, cost_center=platform['cost_center'])]
            platform_lines += [line(pa[head], value) for head,value in tax_heads.items()]
            shop_lines = [line(snap['expense'], total, True, snap['shop_cost_center']), line(shop_credit, total)]
        else:
            tax = amounts['eco_tax']
            # Restaurant place of supply is the restaurant location. Platform state selects IGST vs CGST/SGST.
            tax_heads = split_tax(tax, platform['party']['state'] != snap['shop_party']['state'])
            platform_lines = [line(holding, tax, True)] + [line(pa['eco_'+head], value) for head,value in tax_heads.items()]
            shop_lines = [line(snap['shop_eco'], tax, True), line(shop_credit, tax)]
        pj = journal(platform['company'], platform_lines, 'Local GST '+key, reverse)
        sj = journal(snap['shop_company'], shop_lines, 'Local GST '+key, reverse)
        items = [dict(name=r.item_name, quantity=r.qty, uom=r.uom, taxable=r.net_amount)
                 for r in invoice.items] if invoice else []
        results.append(record(order,snap,values,kind,pj,sj,refund_id,original.name if original else None,items))
    return results


def reverse_refund(order, credit, provider):
    snap = json.loads(order.gst_snapshot)
    refund_id = str(provider['cf_refund_id'])
    from .commission import enabled, earn
    if enabled(snap) and order.status == 'Delivered' and not existing(f'{order.name}:Commission Invoice:'):
        earn(order.name)
    old = existing(f'{order.name}:Commission Credit Note:{refund_id}') or existing(f'{order.name}:Commission Advance Reversal:{refund_id}')
    if old:
        if snap['mode'] == 'Restaurant 9(5)' and not existing(f'{order.name}:Restaurant Credit Note:{refund_id}'):
            reject('Restaurant credit note is missing; review GST accounting')
        if money(json.loads(old.payload)['amounts']['total']) != money(provider['refund_amount']):
            reject('Previously accounted refund changed')
        return
    parts = refund_allocation(order, credit)
    if money(parts['total']) != money(provider['refund_amount']):
        reject('GST refund allocation differs from verified Cashfree refund')
    splits = provider.get('refund_splits') or []
    gateway = json.loads(order.gateway_snapshot or '{}')
    if snap['payment_method'] == 'Cashfree' and (len(splits) != 1 or splits[0].get('vendor_id') != gateway['vendor_id'] or money(splits[0].get('amount')) != money(parts['vendor_amount'])):
        reject('Cashfree refund split does not match commission/GST reversals; review vendor allocation')
    with posting():
        post_documents(order,snap,parts,refund_id,credit)


def refund_allocation(order, credit):
    snap = json.loads(order.gst_snapshot)
    prior = frappe.get_all('LC GST Document', filters={'order':order.name, 'kind':['in', ['Commission Credit Note','Commission Advance Reversal']]}, pluck='payload')
    cumulative = {}
    for payload in prior:
        for key,value in json.loads(payload)['amounts'].items():
            cumulative[key] = money(cumulative.get(key,0)) + money(value)
    base = money(abs(credit.net_total))
    delivery = sum(money(abs(t.tax_amount)) for t in credit.taxes if t.description == 'Delivery charge')
    tax = money(abs(credit.grand_total)) - base - delivery
    if snap['mode'] == 'Restaurant 9(5)' and tax != money((base + delivery) * money('0.05')):
        reject('Restaurant credit note must reverse the corresponding 5% GST')
    if tax < 0:
        reject('Refund components do not balance')
    parts = refund_parts(snap['amounts'], base + money(cumulative.get('base',0)),
        delivery + money(cumulative.get('delivery',0)), tax + money(cumulative.get('supply_tax',0)), cumulative)
    return parts
