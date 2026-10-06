"""Private, on-demand 50 x 30 mm packing labels."""
from io import BytesIO
from urllib.parse import quote
from pathlib import Path

import frappe
from local_commerce.permissions.scope import require_shop
from local_commerce.services.owner import reject
from local_commerce.services.label_access import signature, valid_signature


def render_label(shop_name, recipient, address, order_id, order_date="", delivery_mode="", verification_url=""):
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    from reportlab.pdfbase.pdfmetrics import stringWidth
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(50 * mm, 30 * mm))
    pdf.setTitle("Packing label")

    def lines(text, width, size, limit, font="Helvetica"):
        rows, current = [], ''
        for char in str(text).replace('\n', ' '):
            if stringWidth(current + char, font, size) > width:
                rows.append(current); current = ''
            current += char
        if current:
            rows.append(current)
        if len(rows) > limit:
            rows = rows[:limit]; rows[-1] = rows[-1][:-3] + '...'
        return rows

    # Dedicated brand row: never use the storefront photograph as a logo.
    logo_path = Path(__file__).resolve().parents[1] / 'public' / 'icons' / 'local-wordmark.png'
    pdf.drawImage(ImageReader(str(logo_path)), 18 * mm, 22.5 * mm,
                  width=14 * mm, height=8 * mm, preserveAspectRatio=True,
                  anchor='c', mask='auto')
    pdf.setFont('Helvetica-Bold', 7)
    title = lines(shop_name, 46 * mm, 7, 1, 'Helvetica-Bold')
    pdf.drawCentredString(25 * mm, 21.5 * mm, title[0] if title else '')
    pdf.setFont('Helvetica', 5)
    pdf.drawString(2 * mm, 18.5 * mm, 'ORDER REF ' + order_id[:8].upper())
    pdf.setStrokeColorRGB(.7, .7, .7)
    pdf.setLineWidth(.3)
    pdf.line(2 * mm, 20 * mm, 48 * mm, 20 * mm)
    pdf.setFont('Helvetica-Bold', 7)
    for index, line in enumerate(lines(recipient, 25 * mm, 7, 2, 'Helvetica-Bold')):
        pdf.drawString(2 * mm, (15.3 - index * 2.8) * mm, line)
    pdf.setFont('Helvetica', 5.5)
    for index, line in enumerate(lines(address, 25 * mm, 5.5, 3)):
        pdf.drawString(2 * mm, (10 - index * 2.3) * mm, line)
    # QR grants access only to a limited read-only summary.
    payload = verification_url
    qr = QrCodeWidget(payload, barLevel='L')
    left, bottom, right, top = qr.getBounds()
    size = 19 * mm
    drawing = Drawing(size, size, transform=[size / (right-left), 0, 0, size / (top-bottom), 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, pdf, 29 * mm, 1 * mm)
    # Small footer stays outside the address and QR quiet zone.
    pdf.setFont('Helvetica', 4.5)
    footer = ' / '.join(value for value in (order_date, delivery_mode) if value)
    for line in lines(footer, 25 * mm, 4.5, 1):
        pdf.drawString(2 * mm, 2 * mm, line)
    pdf.showPage(); pdf.save()
    return output.getvalue()


def download(order):
    doc = frappe.get_doc('LC Order', order)
    require_shop(doc.shop, 'write')
    if doc.status not in {'Ready', 'Picked Up', 'Out for Delivery', 'Delivered'}:
        reject('Labels are available once the order is Ready')
    shop = frappe.get_doc('LC Shop', doc.shop)
    snapshot = frappe.parse_json(doc.address_snapshot or '{}')
    address = ', '.join(str(snapshot.get(key) or '').strip() for key in
                        ('line1', 'city', 'postal_code') if snapshot.get(key))
    frappe.local.response.update({
        'filename': 'label-' + doc.name[-10:] + '.pdf',
        'filecontent': render_label(
            shop.shop_name, doc.recipient, address, doc.name,
            frappe.utils.formatdate(doc.creation, 'dd MMM yy'),
            'Scheduled' if doc.delivery_mode == 'Scheduled' else 'Normal',
            frappe.utils.get_url('/local-commerce') + '#/orders/verify/' + quote(doc.name, safe='')
            + '?token=' + signature(frappe.conf.get('encryption_key'), doc.name),
        ),
        'type': 'pdf',
    })
    frappe.local.response['headers'] = {'Cache-Control': 'private, no-store'}


def public_details(order, token):
    if not isinstance(order, str) or not valid_signature(frappe.conf.get('encryption_key'), order, token):
        frappe.throw('This label link is invalid. Ask the shop for a new label.', frappe.PermissionError)
    doc = frappe.get_doc('LC Order', order)
    so = frappe.get_doc('Sales Order', doc.sales_order)
    # Deliberate allowlist: never use the authenticated order serializer here.
    return {
        'name': doc.name,
        'shop_name': frappe.db.get_value('LC Shop', doc.shop, 'shop_name'),
        'status': doc.status,
        'currency': so.currency,
        'total': so.grand_total,
        'items': [{'name': row.item_name, 'quantity': row.qty, 'uom': row.uom,
                   'amount': row.amount} for row in so.items],
    }
