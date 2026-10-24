import csv
import io
import json
import re
from .rules import split_tax
from local_commerce.services.payments.rules import money


def report_row(doc):
    payload = json.loads(doc['payload'])
    snap, values = payload['snapshot'], payload['amounts']
    commission = doc['kind'].startswith('Commission')
    credit = 'Credit Note' in doc['kind']
    taxable = money(values['commission_base']) if commission else money(values['base']) + money(values['delivery'])
    tax = values['commission_tax'] if commission else values['eco_tax']
    heads = doc.get('native_tax_heads') or split_tax(tax, snap['platform']['party']['state'] != snap['shop_party']['state'])
    sign = -1 if credit else 1
    result = dict(invoice=doc.get('sales_invoice') or doc['name'], date=str(doc['posting_date']), kind=doc['kind'],
        original=doc.get('original') or '', order=doc['order'], shop=doc['shop'],
        platform_gstin=snap['platform']['party']['gstin'],
        supplier_gstin=snap['shop_party']['gstin'] if not commission else snap['platform']['party']['gstin'],
        recipient_gstin=snap['shop_party']['gstin'] if commission else '',
        place_of_supply=snap['shop_party']['state'],
        sac=snap['platform']['sac'] if commission else '996331',
        gstr1=('Credit/debit notes (applicable B2B/B2C category)' if credit else
               'B2B' if snap['registration']=='Registered' else 'B2C') if commission else '15 (amendments/credit adjustments as applicable)',
        gstr3b='3.1(a)' if commission else '3.1.1(i)', cash_only=not commission,
        taxable=str(taxable * sign), **{k:str(money(v)*sign) for k,v in heads.items()})
    result['total'] = str((taxable + money(tax)) * sign)
    return result


def csv_bytes(rows):
    if not rows:
        return b'No posted GST documents for this period\n'
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        # Do not allow spreadsheet formulas from user-entered text.
        writer.writerow({key:("'"+str(value) if isinstance(value,str) and (value.lstrip()[:1] in '=+@' or (value.lstrip().startswith('-') and not re.fullmatch(r'-[0-9]+(?:\.[0-9]+)?', value))) else value)
                         for key,value in row.items()})
    return output.getvalue().encode('utf-8-sig')


def pdf(doc):
    from html import escape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    payload = json.loads(doc.payload)
    snap, values = payload['snapshot'], payload['amounts']
    commission = doc.kind.startswith('Commission')
    party = snap['platform']['party']
    recipient = snap['shop_party'] if commission else dict(
        legal_name=payload['customer'].get('recipient') or payload.get('recipient') or 'Customer',
        address=', '.join(str(payload['customer'].get(k) or '') for k in ('line1','city','postal_code')),
        gstin='')
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    def p(text):
        return Paragraph(escape(str(text)),styles['BodyText'])
    rows = [Paragraph(escape(doc.kind),styles['Title']),p(doc.name+' · '+str(doc.posting_date)),Spacer(1,12)]
    for text in [party['legal_name'], party['address'], 'GSTIN: '+party['gstin'],
                 'Bill to: '+recipient['legal_name'], recipient['address'],
                 'Recipient GSTIN: '+(recipient.get('gstin') or 'Unregistered'),
                 'Place of supply: '+snap['shop_party']['state'], 'Order: '+doc.order]:
        rows.append(p(text))
    if doc.original:
        rows.append(p('Credit against: '+doc.original))
    if not commission:
        rows.append(p('Restaurant service supplied by '+snap['shop_party']['legal_name']+'; GST payable by the electronic commerce operator under Section 9(5).'))
        for item in payload.get('items',[]):
            rows.append(p(f"{item['name']} — {abs(item['quantity'])} {item['uom']} — INR {abs(item['taxable']):.2f}"))
    report = report_row(doc.as_dict())
    rows.append(Spacer(1,12))
    entries=[['Description','Amount (INR)'],['SAC',report['sac']],
        ['Commission service' if commission else 'Restaurant service including delivery',str(abs(money(report['taxable'].lstrip('-'))))]]
    entries.append(['GST rate', '18% (9% + 9% intrastate)' if commission else '5% (2.5% + 2.5% intrastate)'])
    for key in ('cgst','sgst','igst','total'):
        entries.append([key.upper(), report[key].lstrip('-')])
    table=Table(entries,colWidths=[330,150]); table.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.5,colors.lightgrey),('BACKGROUND',(0,0),(-1,0),colors.whitesmoke),
        ('PADDING',(0,0),(-1,-1),8)]));rows.append(table)
    rows.append(Spacer(1,12));rows.append(p('Commission rate: '+snap['commission_rate']+'% of food/item value excluding delivery and supply GST. '+('GST included.' if snap['inclusive'] else 'GST charged extra.')))
    SimpleDocTemplate(output,pagesize=A4).build(rows)
    return output.getvalue()
