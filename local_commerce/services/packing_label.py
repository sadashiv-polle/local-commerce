"""Private, on-demand 50 x 30 mm packing labels."""
from io import BytesIO
import json

import frappe
from local_commerce.permissions.scope import require_shop
from local_commerce.services.owner import reject


def render_label(shop_name, recipient, address, order_id, logo=None):
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

    def lines(text, width, size, limit):
        rows, current = [], ''
        for char in str(text).replace('\n', ' '):
            if stringWidth(current + char, 'Helvetica', size) > width:
                rows.append(current); current = ''
            current += char
        if current:
            rows.append(current)
        if len(rows) > limit:
            rows = rows[:limit]; rows[-1] = rows[-1][:-3] + '...'
        return rows

    x = 2 * mm
    if logo:
        try:
            pdf.drawImage(ImageReader(BytesIO(logo)), x, 22 * mm, width=7 * mm,
                          height=6 * mm, preserveAspectRatio=True, anchor='c', mask='auto')
            x = 10 * mm
        except (OSError, ValueError):
            pass
    pdf.setFont('Helvetica-Bold', 7)
    pdf.drawString(x, 25 * mm, lines(shop_name, 48 * mm - x, 7, 1)[0])
    pdf.setFont('Helvetica', 5.5)
    pdf.drawString(2 * mm, 21 * mm, 'ORDER ' + order_id[-10:].upper())
    pdf.setFont('Helvetica-Bold', 7)
    for index, line in enumerate(lines(recipient, 26 * mm, 7, 2)):
        pdf.drawString(2 * mm, (17 - index * 3) * mm, line)
    pdf.setFont('Helvetica', 5.5)
    for index, line in enumerate(lines(address, 26 * mm, 5.5, 4)):
        pdf.drawString(2 * mm, (10 - index * 2.4) * mm, line)
    # Full delivery details remain in QR when printed text must be shortened.
    payload = json.dumps({'order': order_id, 'shop': shop_name, 'customer': recipient,
                          'address': address}, ensure_ascii=False, separators=(',', ':'))
    qr = QrCodeWidget(payload, barLevel='L')
    left, bottom, right, top = qr.getBounds()
    size = 19 * mm
    drawing = Drawing(size, size, transform=[size / (right-left), 0, 0, size / (top-bottom), 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, pdf, 29 * mm, 1 * mm)
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
    logo = None
    # Read only an existing attached File; never fetch arbitrary remote URLs.
    image = shop.get('shop_image')
    if image and image.startswith('/files/'):
        name = frappe.db.get_value('File', {'file_url': image, 'is_private': 0}, 'name')
        if name:
            try:
                file = frappe.get_doc('File', name)
                if (file.file_size or 0) <= 5 * 1024 * 1024:
                    logo = file.get_content()
            except OSError:
                pass
    frappe.local.response.update({
        'filename': 'label-' + doc.name[-10:] + '.pdf',
        'filecontent': render_label(shop.shop_name, doc.recipient, address, doc.name, logo),
        'type': 'pdf',
    })
    frappe.local.response['headers'] = {'Cache-Control': 'private, no-store'}
