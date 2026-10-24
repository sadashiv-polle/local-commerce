"""Version 2 commission billing. Caller holds the LC Order lock.

Old snapshots always use the original journal accounting. New snapshots capture
all billing settings. Native invoices are the only revenue posting in v2.
"""
import json
from html import escape

import frappe
from local_commerce.services.owner import reject
from local_commerce.services.payments.rules import money
from local_commerce.services.payments.accounting import posting, submitted
from .rules import split_tax
from .commission_rules import signed_money


def enabled(snap):
    return snap.get('version') == 2 and bool(snap.get('billing'))


def billing_snapshot(shop, platform):
    from .config import account
    settings = frappe.get_single('LC Store Settings')
    if not settings.get('commission_billing_enabled'):
        return None
    for field in ('commission_receivable','commission_deferred','commission_item'):
        if not settings.get(field):
            reject('Complete platform commission billing settings before enabling')
    if not shop.get('commission_prepaid') or not shop.get('commission_customer'):
        reject('Configure the shop billing Customer and prepaid commission account')
    company = platform['company']
    receivable = frappe.get_doc('Account', settings.get('commission_receivable'))
    if (receivable.company != company or receivable.disabled or receivable.is_group
            or receivable.account_currency != 'INR' or receivable.root_type != 'Asset'
            or receivable.account_type != 'Receivable'):
        reject('Select an active INR Receivable control account for commission invoices')
    deferred = account(settings.get('commission_deferred'), company, 'Liability')
    if deferred in platform['accounts'].values():
        reject('Commission advances require a separate liability account')
    prepaid = account(shop.get('commission_prepaid'), shop.company, 'Asset')
    if prepaid in (shop.get('cashfree_clearing_account'), shop.get('cod_cash_account')):
        reject('Use a separate prepaid commission asset, not a cash or gateway ledger')
    item = frappe.get_doc('Item', settings.get('commission_item'))
    if item.disabled or item.is_stock_item or not item.is_sales_item:
        reject('Select an active non-stock marketplace service item')
    if frappe.db.get_value('UOM', item.stock_uom, 'must_be_whole_number'):
        reject('Use a fractional service UOM for the commission item so partial credit notes are supported')
    if item.get('gst_hsn_code') and item.gst_hsn_code != platform['sac']:
        reject('The commission service item SAC must match the platform SAC')
    customer = frappe.get_doc('Customer', shop.get('commission_customer'))
    if customer.disabled:
        reject('Select an active billing Customer for this vendor')
    if (customer.get('gstin') or '') != (shop.get('gst_number') or ''):
        reject('The billing Customer GSTIN must match the vendor GSTIN')
    other = frappe.db.exists('LC Shop', {'commission_customer': customer.name, 'name': ['!=', shop.name]})
    if other:
        reject('Use a dedicated billing Customer for each shop to isolate statements')
    days = int(settings.get('commission_due_days') or 0)
    if not 0 <= days <= 90:
        reject('Commission payment terms must be between zero and 90 days')
    return dict(customer=customer.name, receivable=receivable.name, deferred=deferred,
                prepaid=prepaid, item=item.name, uom=item.stock_uom, due_days=days)


def party_line(snap, amount, invoice, debit=False):
    from .accounting import line
    row = line(snap['billing']['receivable'], amount, debit)
    row.update(party_type='Customer', party=snap['billing']['customer'],
               reference_type='Sales Invoice', reference_name=invoice)
    return row


def native_invoice(order, snap, values, original=None):
    """Native validation (including India Compliance) is never bypassed."""
    platform, billing = snap['platform'], snap['billing']
    sign = -1 if original else 1
    date = frappe.utils.nowdate() if original else frappe.utils.getdate(order.delivered_at)
    heads = tax_heads(order, snap, values, bool(original))
    customer = frappe.get_doc('Customer', billing['customer'])
    if (customer.get('gstin') or '') != snap['shop_party']['gstin']:
        reject('Vendor billing identity changed after checkout; review the frozen tax details')
    invoice = frappe.get_doc(dict(doctype='Sales Invoice', company=platform['company'],
        customer=billing['customer'], debit_to=billing['receivable'], currency='INR', conversion_rate=1,
        lc_commission_order=order.name, posting_date=date, due_date=frappe.utils.add_days(date, billing['due_days']),
        is_return=int(bool(original)), update_outstanding_for_self=int(snap['payment_method']=='Cashfree'), return_against=original, update_stock=0, disable_rounded_total=1,
        remarks=f"Local dot — Marketplace Services. Shop: {order.shop}. Order: {order.name}",
        items=[dict(item_code=billing['item'], qty=sign*float(money(values['commission_base'])), uom=billing['uom'], conversion_factor=1,
            lc_commission_order=order.name, rate=1, income_account=platform['accounts']['income'],
            cost_center=platform['cost_center'],
            description='Marketplace commission — order '+escape(order.name))],
        taxes=[dict(charge_type='Actual', account_head=platform['accounts'][key],
            description='Commission '+key.upper(), tax_amount=float(money(value)*sign),
            cost_center=platform['cost_center']) for key,value in heads.items() if money(value)]))
    invoice.set_missing_values()
    invoice.calculate_taxes_and_totals()
    if signed_money(invoice.grand_total) != money(values['commission_gross'])*sign:
        reject('Native commission invoice differs from the frozen commission amount')
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def post(order, snap, values, refund_id=''):
    from .accounting import existing, record, journal, line
    reverse = bool(refund_id)
    billing, platform = snap['billing'], snap['platform']
    pa = platform['accounts']
    online = snap['payment_method'] == 'Cashfree'
    original = existing(f'{order.name}:Commission Invoice:')
    # Cashfree withholding is recorded at payment; revenue is earned on delivery.
    advance = not original and order.status != 'Delivered'
    if advance and not online:
        return None
    kind = ('Commission Advance Reversal' if reverse else 'Commission Advance') if advance else (
        'Commission Credit Note' if reverse else 'Commission Invoice')
    old = existing(f'{order.name}:{kind}:{refund_id}')
    if old:
        if json.loads(old.payload)['amounts'] != values:
            reject('Previously posted commission amounts changed')
        return old
    total, base, tax = (money(values[k]) for k in ('commission_gross','commission_base','commission_tax'))
    if total == 0:
        return record(order, snap, values, kind, None, None, refund_id, original.name if original else None)
    heads = tax_heads(order, snap, values, reverse)
    gateway = json.loads(order.gateway_snapshot or '{}')
    shop_credit = gateway.get('clearing_account') if online else snap['shop_payable']
    invoice, pj = None, None
    if advance:
        if reverse and not existing(f'{order.name}:Commission Advance:'):
            reject('Original commission advance is missing')
        # GST on the advance is kept separate from deferred service income.
        lines = [line(pa['clearing'], total, True), line(billing['deferred'], base)]
        lines += [line(pa[k], v) for k,v in heads.items()]
        pj = journal(platform['company'], lines, 'Commission advance '+order.name, reverse)
        shop_lines = [line(billing['prepaid'], total, True), line(shop_credit, total)]
    else:
        if reverse and (not original or not original.get('sales_invoice')):
            reject('Original native commission invoice is missing')
        invoice = native_invoice(order, snap, values, original.sales_invoice if reverse else None)
        if online:
            if not reverse:
                if not existing(f'{order.name}:Commission Advance:'):
                    reject('Verified commission advance is missing')
                lines = [line(billing['deferred'], base, True)]
                lines += [line(pa[k], v, True) for k,v in heads.items()]
                lines += [party_line(snap, total, invoice.name)]
            else:
                # Cashfree returns the withheld amount; clear the native credit balance.
                lines = [party_line(snap, total, invoice.name, True), line(pa['clearing'], total)]
            pj = journal(platform['company'], lines, 'Commission allocation '+order.name)
        shop_lines = [line(snap['expense'], total, True, snap['shop_cost_center']),
                      line(billing['prepaid'] if online and not reverse else shop_credit, total)]
    sj = journal(snap['shop_company'], shop_lines, 'Commission '+order.name+' '+refund_id, reverse)
    return record(order, snap, values, kind, pj, sj, refund_id,
        original.name if reverse and original else None,
        sales_invoice=invoice.name if invoice else None)


def earn(order):
    """Background retry boundary: failures never undo a successful delivery."""
    doc = frappe.get_doc('LC Order', order, for_update=True)
    snap = json.loads(doc.get('gst_snapshot') or '{}')
    if not enabled(snap) or doc.status != 'Delivered':
        return
    if not doc.sales_invoice:
        reject('Product invoice is missing')
    if doc.payment_method == 'Cashfree' and (doc.payment_status not in ('Paid','Refunded') or not doc.payment_entry):
        reject('Cashfree payment must be verified before earning commission')
    if doc.payment_method == 'Cash on Delivery' and doc.payment_status not in ('Collected', 'Reconciled'):
        reject('Record COD collection before earning commission')
    if doc.payment_method == 'Manual UPI' and doc.payment_status not in ('Paid', 'Reconciled'):
        reject('Verify Manual UPI before earning commission')
    submitted('Sales Invoice', doc.sales_invoice)
    with posting():
        post(doc, snap, snap['amounts'])
        frappe.db.set_value('LC Order', doc.name, {'commission_pending':0, 'commission_error':None, 'commission_attempted_at':frappe.utils.now_datetime()}, update_modified=False)


def process(order):
    frappe.db.savepoint('commission_earn')
    try:
        earn(order)
    except Exception:
        frappe.db.rollback(save_point='commission_earn')
        ref = frappe.log_error(title='Local commission billing', message=frappe.get_traceback())
        frappe.db.set_value('LC Order', order, {
            'commission_error':'Commission billing needs administrator review. Error reference: '+str(ref.name if ref else ''),
            'commission_attempted_at':frappe.utils.now_datetime()}, update_modified=False)


def recover():
    for name in frappe.get_all('LC Order', filters={'commission_pending':1, 'status':'Delivered'},
            pluck='name', order_by='commission_attempted_at asc, creation asc', limit_page_length=100):
        frappe.enqueue('local_commerce.services.gst.commission.process', order=name,
                       job_id='lc-commission-'+name, deduplicate=True, enqueue_after_commit=True)


def protect_cancel(doc, method=None):
    """Do not silently cancel one side of a cross-company accounting event."""
    linked = False
    if doc.doctype == 'Sales Invoice':
        linked = frappe.db.exists('LC GST Document', {'sales_invoice':doc.name})
    elif doc.doctype == 'Payment Entry':
        linked = doc.get('lc_commission_key')
    elif doc.doctype == 'Journal Entry':
        linked = (frappe.db.exists('Payment Entry', {'lc_commission_shop_journal':doc.name, 'docstatus':1})
                  or frappe.db.exists('LC GST Document', {'platform_journal':doc.name, 'sales_invoice':['is','set']})
                  or frappe.db.exists('LC GST Document', {'shop_journal':doc.name, 'sales_invoice':['is','set']}))
    if linked:
        reject('This document is part of linked marketplace commission accounting. Use a commission credit/refund or an accountant-reviewed reversal of both Companies; do not cancel one side.')


def tax_heads(order, snap, values, reverse=False):
    """Cumulative rounding keeps repeated credit notes within each GST head."""
    interstate = snap['platform']['party']['state'] != snap['shop_party']['state']
    prior = money(0)
    if reverse:
        for payload in frappe.get_all('LC GST Document', filters={'order':order.name,
                'kind':['in',['Commission Credit Note','Commission Advance Reversal']]}, pluck='payload'):
            prior += money(json.loads(payload)['amounts']['commission_tax'])
    before = split_tax(prior, interstate)
    after = split_tax(prior+money(values['commission_tax']), interstate)
    return {head:str(money(after[head])-money(before[head])) for head in before}
