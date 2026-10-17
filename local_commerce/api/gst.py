"""Admin-only GST configuration and filing workpapers; no automatic portal filing."""
import json
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject
from local_commerce.services.gst import config
from local_commerce.services.payments.rules import money


@frappe.whitelist(methods=['GET'])
def settings():
    require_platform()
    doc = frappe.get_single('LC Store Settings')
    return dict(platform={f:doc.get(f) for f in config.PLATFORM_FIELDS},
        shops=frappe.get_all('LC Shop',fields=['name','shop_name','company',*config.SHOP_FIELDS],limit_page_length=0),
        companies=frappe.get_all('Company',pluck='name'),
        cost_centers=frappe.get_all('Cost Center',filters={'is_group':0},fields=['name','company'],limit_page_length=0),
        accounts=frappe.get_all('Account',filters={'disabled':0,'is_group':0,'account_currency':'INR'},
            fields=['name','company','root_type','account_type'],limit_page_length=0))


def values_arg(values, allowed):
    values=frappe.parse_json(values)
    if not isinstance(values,dict) or set(values)-set(allowed):
        reject('Invalid GST settings')
    for key in ('gst_enabled','gst_commission_inclusive'):
        if key in values:
            if str(values[key]) not in ('0','1','True','False','true','false'):
                reject('Invalid GST checkbox')
            values[key] = int(str(values[key]) in ('1','True','true'))
    return values


@frappe.whitelist(methods=['POST'])
def save_platform(values):
    require_platform()
    doc=frappe.get_single('LC Store Settings')
    doc.update(values_arg(values,config.PLATFORM_FIELDS))
    doc.save(ignore_permissions=True)
    for name in frappe.get_all('LC Shop',filters={'gst_enabled':1},pluck='name',limit_page_length=0):
        config.validate_shop(frappe.get_doc('LC Shop',name))
    return {'saved':True,'note':'Draft until a shop is explicitly enabled'}


@frappe.whitelist(methods=['POST'])
def save_shop(shop,values):
    require_platform()
    doc=frappe.get_doc('LC Shop',shop,for_update=True)
    doc.update(values_arg(values,config.SHOP_FIELDS))
    doc.save(ignore_permissions=True)
    return {'saved':True}


def documents(start,end):
    start,end=frappe.utils.getdate(start),frappe.utils.getdate(end)
    if end<start or (end-start).days>366:
        reject('Choose a reporting period of up to one year')
    return frappe.get_all('LC GST Document', filters={'posting_date':['between',[start,end]]},
        fields=['name','posting_date','kind','original','order','shop','payload','platform_journal','shop_journal'],
        order_by='posting_date asc, name asc',limit_page_length=0)


@frappe.whitelist(methods=['GET'])
def report(start,end,download=0):
    require_platform()
    from local_commerce.services.gst.reports import report_row,csv_bytes
    docs=documents(start,end)
    from local_commerce.services.payments.accounting import submitted
    for doc in docs:
        for field in ('platform_journal', 'shop_journal'):
            if doc.get(field):
                submitted('Journal Entry', doc[field])
    rows=[report_row(doc) for doc in docs]
    if str(download)=='1':
        frappe.local.response.update(type='download',filename='local-gst-workpaper.csv',filecontent=csv_bytes(rows))
        return
    return dict(rows=rows,note='CA-review workpaper, not GST portal upload JSON. Restaurant liability is cash-only. Credit notes require the applicable return-period adjustment.',
        documents=[{k:v for k,v in d.items() if k!='payload'} for d in docs])


@frappe.whitelist(methods=['GET'])
def invoice(name):
    from local_commerce.services import orders
    from local_commerce.services.gst.reports import pdf
    doc=frappe.get_doc('LC GST Document',name)
    order=frappe.get_doc('LC Order',doc.order)
    orders.authorize(order,write=doc.kind.startswith('Commission'))
    frappe.local.response.update(type='pdf',filename=doc.name+'.pdf',filecontent=pdf(doc))


@frappe.whitelist(methods=['POST'])
def record_platform_bank(order, net, fee, fee_tax, utr, date, evidence):
    """Explicit per-order allocation from the merchant statement, never an entire batch."""
    require_platform()
    from local_commerce.services.payments.accounting import state,persist,posting,submitted
    from local_commerce.services.gst.accounting import existing,journal,line
    doc=frappe.get_doc('LC Order',order,for_update=True)
    if not doc.gst_snapshot or doc.payment_method!='Cashfree' or not doc.payment_entry:
        reject('Select a paid Cashfree order with GST accounting')
    if not existing(f'{order}:Commission Invoice:'):
        reject('Complete original GST accounting before posting its bank receipt')
    if money(doc.gateway_refunded_amount or 0):
        reject('Refunded settlement allocations require native bank reconciliation')
    snap=json.loads(doc.gst_snapshot);amounts=snap['amounts']; platform=snap['platform'];pa=platform['accounts']
    net,fee,fee_tax=map(money,(net,fee,fee_tax))
    if net+fee+fee_tax != money(amounts['commission_gross'])+money(amounts['eco_tax']):
        reject('Net receipt and charges must equal this order’s retained commission plus restaurant GST')
    if not str(utr).strip() or not str(evidence).strip() or len(str(evidence))>1000:
        reject('Enter the bank UTR and the statement/invoice allocation reference')
    data=state(doc); allocation=dict(net=str(net),fee=str(fee),fee_tax=str(fee_tax),utr=str(utr),date=str(frappe.utils.getdate(date)),evidence=str(evidence))
    if data.get('gst_platform_settlement'):
        old=data['gst_platform_settlement']
        if old['allocation']!=allocation:
            reject('Settlement already posted with different amounts')
        submitted('Journal Entry',old['journal']);return old
    with posting():
        je=journal(platform['company'],[line(pa['bank'],net,True),line(pa['fee'],fee,True,platform['cost_center']),
            line(pa['fee_tax'],fee_tax,True,platform['cost_center']),line(pa['clearing'],net+fee+fee_tax)],
            'Local platform settlement '+doc.name+' UTR '+str(utr)+' statement '+str(evidence), posting_date=allocation['date'], utr=str(utr))
        data['gst_platform_settlement']=dict(allocation=allocation,journal=je)
        persist(doc,data)
    return data['gst_platform_settlement']


@frappe.whitelist(methods=['POST'])
def record_shop_remittance(order, shop_bank, utr, date):
    require_platform()
    from local_commerce.services.payments.accounting import state,persist,posting,submitted
    from local_commerce.services.gst.accounting import existing,journal,line
    doc=frappe.get_doc('LC Order',order,for_update=True)
    if not doc.gst_snapshot or doc.payment_method=='Cashfree':
        reject('Select a COD or Manual UPI order with GST accounting')
    if not existing(f'{order}:Commission Invoice:'):
        reject('The commission invoice has not been posted')
    snap=json.loads(doc.gst_snapshot);platform=snap['platform'];pa=platform['accounts']
    config.account(shop_bank,snap['shop_company'],'Asset',True)
    if not str(utr).strip():
        reject('Enter the completed bank-transfer UTR')
    amount=money(snap['amounts']['commission_gross'])+money(snap['amounts']['eco_tax'])
    for payload in frappe.get_all('LC GST Document',filters={'order':order,'kind':'Commission Credit Note'},pluck='payload'):
        values=json.loads(payload)['amounts'];amount-=money(values['commission_gross'])+money(values['eco_tax'])
    data=state(doc);allocation=dict(amount=str(amount),shop_bank=shop_bank,utr=str(utr),date=str(frappe.utils.getdate(date)))
    if data.get('gst_remittance'):
        old=data['gst_remittance']
        if old['allocation']!=allocation:
            reject('Remittance already posted; use native reconciliation for subsequent adjustments')
        for key in ('platform_journal','shop_journal'):
            submitted('Journal Entry',old[key])
        return old
    if amount<=0:
        reject('No positive amount remains due')
    with posting():
        pj=journal(platform['company'],[line(pa['bank'],amount,True),line(pa['receivable'],amount)],'Shop remittance '+order+' UTR '+str(utr), posting_date=allocation['date'], utr=str(utr))
        sj=journal(snap['shop_company'],[line(snap['shop_payable'],amount,True),line(shop_bank,amount)],'Platform remittance '+order+' UTR '+str(utr), posting_date=allocation['date'], utr=str(utr))
        data['gst_remittance']=dict(allocation=allocation,platform_journal=pj,shop_journal=sj)
        persist(doc,data)
    return data['gst_remittance']


@frappe.whitelist(methods=['POST'])
def record_manual_refund(order,credit_note,payment_entry):
    require_platform()
    from local_commerce.services.gst.accounting import reverse_refund
    doc=frappe.get_doc('LC Order',order,for_update=True)
    if not doc.gst_snapshot or doc.payment_method=='Cashfree' or not doc.sales_invoice:
        reject('Use verified Cashfree refunds for online payments; select an invoiced manual-payment order')
    credit=frappe.get_doc('Sales Invoice',credit_note)
    payment=frappe.get_doc('Payment Entry',payment_entry)
    original=frappe.get_doc('Sales Invoice',doc.sales_invoice)
    if (credit.docstatus!=1 or not credit.is_return or credit.return_against!=original.name
            or credit.company!=original.company or credit.customer!=original.customer
            or credit.currency!='INR' or credit.grand_total>=0 or payment.docstatus!=1
            or payment.payment_type!='Pay' or payment.company!=original.company
            or payment.paid_from_account_currency!='INR' or payment.paid_to_account_currency!='INR'
            or payment.party!=original.customer or payment.party_type!='Customer'
            or money(payment.paid_amount)!=money(abs(credit.grand_total))
            or len(payment.references)!=1 or payment.references[0].reference_doctype!='Sales Invoice'
            or payment.references[0].reference_name!=credit.name
            or money(abs(payment.references[0].allocated_amount))!=money(abs(credit.grand_total))):
        reject('Select the submitted credit note and matching refund Payment Entry for this order')
    reverse_refund(doc,credit,dict(cf_refund_id='manual-'+credit.name,refund_amount=abs(credit.grand_total)))
    return {'posted':True}
