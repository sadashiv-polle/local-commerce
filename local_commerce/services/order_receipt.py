"""Authenticated printable order summary, using original ERPNext order amounts."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import frappe
from local_commerce.permissions.scope import require_shop


def render_receipt(data):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
    output = BytesIO()
    width, margin = 80 * mm, 4 * mm
    content = width - 2 * margin
    styles = {
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=8, leading=11),
        'center': ParagraphStyle('center', fontName='Helvetica', fontSize=8, leading=11, alignment=1),
        'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=13, leading=16, alignment=1),
        'bold': ParagraphStyle('bold', fontName='Helvetica-Bold', fontSize=10, leading=13),
        'small': ParagraphStyle('small', fontName='Helvetica', fontSize=6, leading=8, alignment=1),
    }
    def text(value, style='body'):
        return Paragraph(escape(str(value or '')), styles[style])
    def money(value):
        return f"{float(value or 0):,.2f}"
    def rule():
        return HRFlowable(width=content, thickness=.5, spaceBefore=0, spaceAfter=0)
    def pair(label, value, bold=False):
        row = Table([[text(label, 'bold' if bold else 'body'), text(value, 'bold' if bold else 'body')]],
                    colWidths=[content * .63, content * .37])
        row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
        return row
    logo = Path(__file__).resolve().parents[1] / 'public/icons/local-wordmark.png'
    image = Image(str(logo), width=72, height=39)
    story = [image, text(data['shop'], 'title'), text('ORDER RECEIPT', 'center'),
             Spacer(1, 6), rule(), Spacer(1, 6),
             text('Order: ' + data['order'][-10:].upper(), 'bold'),
             text(data['created']), text('Status: ' + data['status']),
             text('Customer: ' + data['customer']), text(data['address']),
             Spacer(1, 6), rule(), Spacer(1, 5),
             text('ITEM / QTY × RATE                        AMOUNT', 'small')]
    for row in data['items']:
        story += [text(row['name']), pair(f"{row['qty']:g} {row['uom']} x {money(row['rate'])}",
                                          money(row['amount'])), Spacer(1, 4)]
    story += [rule(), Spacer(1, 5), text('Currency: ' + data['currency']),
              pair('Subtotal', money(data['subtotal'])),
              pair('Tax + delivery', money(data['charges']))]
    if data['discount']:
        story.append(pair('Discount', money(data['discount'])))
    story += [rule(), pair('TOTAL', money(data['total']), True), rule(), Spacer(1, 6),
              text('Payment: ' + data['method']), text('Payment status: ' + data['payment_status']),
              Spacer(1, 8), text('Thank you for shopping local.', 'center'),
              text('Order summary — not a tax invoice or independent proof of payment.', 'small'),
              Spacer(1, 4), text('Full order ID: ' + data['order'], 'small')]
    # Measure wrapped content first so roll length fits the order without A4 whitespace.
    measured = [(flow, *flow.wrap(content, 100000)) for flow in story]
    height = sum(h for _, _, h in measured) + 2 * margin
    pdf = canvas.Canvas(output, pagesize=(width, height))
    pdf.setTitle('80 mm order receipt')
    y = height - margin
    for flow, w, h in measured:
        y -= h
        flow.drawOn(pdf, margin + max(0, (content - w) / 2), y)
    pdf.showPage()
    pdf.save()
    return output.getvalue()


def download(order):
    doc = frappe.get_doc('LC Order', order)
    require_shop(doc.shop)
    so = frappe.get_doc('Sales Order', doc.sales_order)
    address = frappe.parse_json(doc.address_snapshot or '{}')
    data = {
        'shop': frappe.db.get_value('LC Shop', doc.shop, 'shop_name'),
        'order': doc.name, 'created': str(doc.creation), 'status': doc.status,
        'customer': doc.recipient, 'address': ', '.join(str(address.get(k) or '') for k in
            ('line1', 'city', 'postal_code') if address.get(k)),
        'currency': so.currency, 'subtotal': so.total, 'charges': so.total_taxes_and_charges,
        'discount': so.discount_amount, 'total': so.grand_total,
        'method': doc.payment_method, 'payment_status': doc.payment_status,
        'items': [{'name': row.item_name, 'qty': float(row.qty), 'uom': row.uom,
                   'rate': row.rate, 'amount': row.amount} for row in so.items],
    }
    frappe.local.response.update({'type': 'pdf', 'filename': 'receipt-' + doc.name[-10:] + '.pdf',
                                  'filecontent': render_receipt(data)})
