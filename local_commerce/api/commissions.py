"""Scoped commission statements; only administrators can record money received."""
import hashlib
import json
import frappe
from local_commerce.permissions.scope import require_platform, require_shop
from local_commerce.services.owner import reject
from local_commerce.services.payments.rules import money
from local_commerce.services.gst.commission_rules import signed_money
from local_commerce.services.payments.accounting import posting, submitted


def rows(start, end, shop='', method='', order=''):
    start, end = frappe.utils.getdate(start), frappe.utils.getdate(end)
    if end < start or (end-start).days > 366:
        reject('Choose a period of up to one year')
    if shop:
        require_shop(shop, 'write')
    else:
        require_platform()
    filters = {'posting_date':['between',[start,end]], 'kind':['in',['Commission Invoice','Commission Credit Note']]}
    if shop:
        filters['shop'] = shop
    if order:
        filters['order'] = order
    if method and method not in ('Cashfree','Cash on Delivery','Manual UPI'):
        reject('Select a valid payment method')
    result = []
    docs = frappe.get_all('LC GST Document', filters=filters,
            fields=['name','shop','order','posting_date','kind','payload','sales_invoice','delivered_at'],
            order_by='posting_date desc, name desc', limit_page_length=0)
    names = [d.order for d in docs]
    order_data = {r.name:r for r in frappe.get_all('LC Order', filters={'name':['in',names]},
        fields=['name','status','gateway_accounting_json'],limit_page_length=0)} if names else {}
    shops = {r.name:r.shop_name for r in frappe.get_all('LC Shop',filters={'name':['in',list({d.shop for d in docs})]},
        fields=['name','shop_name'],limit_page_length=0)} if docs else {}
    invoice_names = [d.sales_invoice for d in docs if d.sales_invoice]
    invoices = {r.name:r for r in frappe.get_all('Sales Invoice',filters={'name':['in',invoice_names]},
        fields=['name','outstanding_amount','due_date','docstatus'],limit_page_length=0)} if invoice_names else {}
    for doc in docs:
        payload = json.loads(doc.payload)
        snap, values = payload['snapshot'], payload['amounts']
        if method and snap['payment_method'] != method:
            continue
        current_order = order_data.get(doc.order) or {}
        allocation = json.loads(current_order.get('gateway_accounting_json') or '{}').get('gst_platform_settlement') or {}
        credit = doc.kind == 'Commission Credit Note'
        sign = -1 if credit else 1
        invoice = invoices.get(doc.sales_invoice)
        native = bool(invoice and invoice.docstatus == 1)
        zero = snap.get('version') == 2 and money(values['commission_gross']) == 0
        outstanding = signed_money(invoice.outstanding_amount) if native else money(0) if zero else None
        result.append(dict(document=doc.name, invoice=doc.sales_invoice or '', shop=doc.shop,
            shop_name=shops.get(doc.shop,doc.shop), order=doc.order,
            date=str(doc.posting_date), delivered_at=str(doc.delivered_at or ''),
            method=snap['payment_method'], kind=doc.kind, rate=snap['commission_rate'],
            order_amount=str(money(values['total'])*sign),
            commission=str(money(values['commission_base'])*sign), gst=str(money(values['commission_tax'])*sign),
            total=str(money(values['commission_gross'])*sign),
            outstanding=str(outstanding) if outstanding is not None else None,
            due_date=str(invoice.due_date or '') if invoice else '',
            status=('Review native invoice' if doc.sales_invoice and not native else 'No commission charge' if zero else 'Legacy journal' if not native else
                    'Credit balance' if outstanding < 0 else 'Settled' if outstanding == 0 else 'Outstanding'),
            overdue=bool(native and outstanding > 0 and invoice.due_date and frappe.utils.getdate(invoice.due_date) < frappe.utils.getdate()),
            completed=current_order.get('status') == 'Delivered',
            bank_received=bool(allocation) and not credit,
            settlement_reference=allocation.get('allocation',{}).get('utr','')))
    return result


@frappe.whitelist(methods=['GET'])
def report(start, end, shop='', method='', order='', download=0):
    data = rows(start,end,shop,method,order)
    if str(download) == '1':
        from local_commerce.services.gst.reports import csv_bytes
        frappe.local.response.update(type='download',filename='commission-statement.csv',filecontent=csv_bytes(data))
        return
    totals = {key:str(sum((signed_money(r[key]) for r in data),money(0))) for key in ('commission','gst','total')}
    totals['outstanding'] = str(sum((signed_money(r['outstanding']) for r in data if r['outstanding'] is not None),money(0)))
    totals['cod_outstanding'] = str(sum((signed_money(r['outstanding']) for r in data if r['outstanding'] is not None and r['method']=='Cash on Delivery'),money(0)))
    totals['overdue'] = str(sum((signed_money(r['outstanding']) for r in data if r['overdue']),money(0)))
    totals['online_sales'] = str(sum((signed_money(r['order_amount']) for r in data if r['method']=='Cashfree'),money(0)))
    totals['cod_sales'] = str(sum((signed_money(r['order_amount']) for r in data if r['method']=='Cash on Delivery'),money(0)))
    totals['orders'] = len({r['order'] for r in data if r['kind']=='Commission Invoice' and r['completed']})
    totals['online_bank_received'] = str(sum((signed_money(r['total']) for r in data if r['bank_received']),money(0)))
    balances = {}
    for row in data:
        balances.setdefault(row['shop'],{'name':row['shop_name'],'amount':money(0)})
        if row['outstanding'] is not None:
            balances[row['shop']]['amount'] += signed_money(row['outstanding'])
    return dict(rows=data, totals=totals, balances={k:{'name':v['name'],'amount':str(v['amount'])} for k,v in balances.items()},
        note='Invoice-period statement. Legacy journal balances are excluded from native outstanding totals. Settled invoices can include gateway clearing allocations; this does not confirm a bank payout.')


@frappe.whitelist(methods=['POST'])
def receive(document, amount, bank, shop_bank, utr, date):
    require_platform()
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    from local_commerce.services.gst.config import account
    from local_commerce.services.gst.accounting import journal, line
    ledger = frappe.get_doc('LC GST Document', document)
    if not ledger.sales_invoice or ledger.kind != 'Commission Invoice':
        reject('Select a native commission invoice')
    # Lock order before invoice, matching refund and delivery accounting.
    frappe.get_doc('LC Order', ledger.order, for_update=True)
    invoice = frappe.get_doc('Sales Invoice', ledger.sales_invoice, for_update=True)
    submitted('Sales Invoice', invoice.name)
    snap = json.loads(ledger.payload)['snapshot']
    if snap['payment_method'] == 'Cashfree':
        reject('Cashfree allocations use gateway settlement reconciliation')
    account(bank,invoice.company,'Asset',True)
    account(shop_bank,snap['shop_company'],'Asset',True)
    amount = money(amount)
    utr = str(utr or '').strip()
    date = str(frappe.utils.getdate(date))
    if not utr or len(utr)>140 or amount <= 0 or frappe.utils.getdate(date)>frappe.utils.getdate():
        reject('Enter a positive received amount, bank reference and completed payment date')
    key = hashlib.sha256((invoice.name+'\n'+utr).encode()).hexdigest()
    old = frappe.db.get_value('Payment Entry', {'lc_commission_key':key}, 'name')
    if old:
        payment = frappe.get_doc('Payment Entry', old)
        if (payment.docstatus != 1 or money(payment.paid_amount) != amount or payment.paid_to != bank
                or str(payment.reference_date) != date or payment.get('lc_commission_shop_bank') != shop_bank):
            reject('This reference was already recorded with different details or cancelled; review it in ERPNext')
        submitted('Journal Entry', payment.lc_commission_shop_journal)
        return dict(payment_entry=old)
    if amount > signed_money(invoice.outstanding_amount):
        reject('Amount exceeds this invoice’s current outstanding balance')
    with posting():
        payment = get_payment_entry('Sales Invoice', invoice.name, party_amount=float(amount), bank_account=bank)
        payment.reference_no = utr
        payment.reference_date = date
        payment.posting_date = date
        payment.lc_commission_key = key
        payment.lc_commission_shop_bank = shop_bank
        payment.lc_commission_order = ledger.order
        payment.insert(ignore_permissions=True)
        if money(payment.paid_amount) != amount or money(payment.total_allocated_amount) != amount:
            reject('Native payment allocation differs from the received amount')
        payment.submit()
        je = journal(snap['shop_company'],[line(snap['shop_payable'],amount,True),line(shop_bank,amount)],
            'Commission remittance '+invoice.name+' UTR '+utr, posting_date=date, utr=utr)
        frappe.db.set_value('Payment Entry', payment.name, 'lc_commission_shop_journal', je, update_modified=False)
    return dict(payment_entry=payment.name)


@frappe.whitelist(methods=['GET'])
def history(document):
    ledger = frappe.get_doc('LC GST Document', document)
    require_shop(ledger.shop, 'write')
    if not ledger.sales_invoice:
        return dict(payments=[], note='Historical journal accounting; review through GST workpapers')
    # Fixed query; never expose other invoices or counterparties in the same payment.
    payments = frappe.db.sql('''select p.name,p.posting_date,p.reference_no,r.allocated_amount
        from `tabPayment Entry` p join `tabPayment Entry Reference` r on r.parent=p.name
        where p.docstatus=1 and r.reference_doctype='Sales Invoice' and r.reference_name=%s
        order by p.posting_date,p.name''', (ledger.sales_invoice,), as_dict=True)
    return dict(payments=payments, note='Native Payment Entries; gateway clearing allocations are shown on the invoice ledger.')


@frappe.whitelist(methods=['GET'])
def advance_workpaper(start, end, download=0):
    """Separate receipt-tax and invoice adjustments; not a GST portal upload."""
    require_platform()
    from local_commerce.services.gst.reports import csv_bytes
    from local_commerce.services.gst.rules import split_tax
    start,end = frappe.utils.getdate(start),frappe.utils.getdate(end)
    if end < start or (end-start).days > 366:
        reject('Choose a period of up to one year')
    output=[]
    for row in frappe.get_all('LC GST Document',filters={'posting_date':['between',[start,end]],
            'kind':['in',['Commission Advance','Commission Advance Reversal','Commission Invoice']]},
            fields=['name','order','shop','posting_date','kind','payload','platform_journal','sales_invoice'],limit_page_length=0):
        payload=json.loads(row.payload);snap=payload['snapshot'];values=payload['amounts']
        if snap.get('version') != 2 or snap['payment_method'] != 'Cashfree':
            continue
        if row.platform_journal:
            submitted('Journal Entry',row.platform_journal)
        if row.sales_invoice:
            submitted('Sales Invoice',row.sales_invoice)
        sign=1 if row.kind=='Commission Advance' else -1
        heads=split_tax(values['commission_tax'],snap['platform']['party']['state'] != snap['shop_party']['state'])
        if row.platform_journal:
            journal = frappe.get_doc('Journal Entry', row.platform_journal)
            heads = {head:str(abs(sum((signed_money(r.credit_in_account_currency)-signed_money(r.debit_in_account_currency) for r in journal.accounts if r.account == snap['platform']['accounts'][head]),money(0)))) for head in ('cgst','sgst','igst')}
        output.append(dict(date=str(row.posting_date),document=row.name,order=row.order,shop=row.shop,kind=row.kind,
            invoice=row.sales_invoice or '',journal=row.platform_journal or '',
            taxable_advance=str(money(values['commission_base'])*sign),
            **{key:str(money(value)*sign) for key,value in heads.items()},
            note='Invoice adjustment offsets advance GST; include native invoice tax separately. CA review required.'))
    if str(download)=='1':
        frappe.local.response.update(type='download',filename='commission-advance-tax-workpaper.csv',filecontent=csv_bytes(output))
        return
    return dict(rows=output)


@frappe.whitelist(methods=['GET'])
def tcs_review(start, end):
    """Order-level classification workpaper, deliberately not a GSTR-8 liability."""
    require_platform()
    from local_commerce.services.gst.reports import csv_bytes
    start,end=frappe.utils.getdate(start),frappe.utils.getdate(end)
    if end < start or (end-start).days > 366:
        reject('Choose a period of up to one year')
    result=[]
    for doc in frappe.get_all('LC Order',filters={'creation':['between',[start,frappe.utils.add_days(end,1)]],
            'gst_snapshot':['is','set']},fields=['name','shop','creation','payment_method','payment_status',
                'status','gst_snapshot','gateway_refunded_amount'],limit_page_length=0):
        snap=json.loads(doc.gst_snapshot or '{}')
        if not snap:
            continue
        mode=snap['mode']
        reason=('Section 9(5): review separately from TCS' if mode=='Restaurant 9(5)' else
                'Exempt goods: review exemption; not ordinary taxable supplies' if mode=='Exempt goods' else
                'Shop collects COD/Manual UPI: confirm who collects consideration' if doc.payment_method!='Cashfree' else
                'Potential operator-collected taxable supply: confirm TCS eligibility, registration and effective rate')
        result.append(dict(order=doc.name,shop=doc.shop,order_created=str(doc.creation),
            order_status=doc.status,payment_status=doc.payment_status,method=doc.payment_method,
            vendor_gstin=snap['shop_party']['gstin'],registration=snap['registration'],supply_treatment=mode,
            item_base=snap['amounts']['base'],delivery=snap['amounts']['delivery'],
            supply_tax=snap['amounts']['supply_tax'],commission_gst=snap['amounts']['commission_tax'],
            cashfree_refunded=str(doc.gateway_refunded_amount or 0),review=reason,
            tcs_amount='Not calculated',note='Order-creation period only; not collection-period GSTR-8. Reconcile actual collections and return dates.'))
    frappe.local.response.update(type='download',filename='tcs-classification-review.csv',filecontent=csv_bytes(result))
