"""Authenticated printable order summary, using original ERPNext order amounts."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import frappe
from local_commerce.permissions.scope import require_shop


def render_receipt(data):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    output = BytesIO()
    styles = getSampleStyleSheet()
    def text(value, style='Normal'):
        return Paragraph(escape(str(value or '')), styles[style])
    def money(value):
        return f"{data['currency']} {float(value or 0):,.2f}"
    logo = Path(__file__).resolve().parents[1] / 'public/icons/local-wordmark.png'
    image = Image(str(logo), width=90, height=48)
    image.hAlign = 'LEFT'
    story = [image, text(data['shop'], 'Heading1'), text('ORDER RECEIPT', 'Heading2'),
             text('Order ID: ' + data['order']), text('Order date: ' + data['created']),
             text('Order status: ' + data['status']), Spacer(1, 12),
             text('Customer: ' + data['customer']), text(data['address']), Spacer(1, 16)]
    rows = [[text(value) for value in ['Item', 'Qty / unit', 'Rate', 'Amount']]]
    for row in data['items']:
        rows.append([text(row['name']), text(f"{row['qty']:g} {row['uom']}"),
                     text(money(row['rate'])), text(money(row['amount']))])
    table = Table(rows, colWidths=[230, 75, 95, 95], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f2eb')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#dce4de')),
    ]))
    story += [table, Spacer(1, 14), text('Item subtotal: ' + money(data['subtotal'])),
              text('Taxes and delivery charges: ' + money(data['charges'])),
              text('Additional discount: ' + money(data['discount'])),
              text('Order total: ' + money(data['total']), 'Heading2'),
              text('Payment method: ' + data['method']), text('Payment status: ' + data['payment_status']),
              Spacer(1, 14), text('This is an order summary, not a tax invoice or independent proof of payment.'),
              text('Thank you for shopping local.')]
    SimpleDocTemplate(output, pagesize=A4, leftMargin=50, rightMargin=50,
                      topMargin=30, bottomMargin=35, title='Order receipt').build(story)
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
