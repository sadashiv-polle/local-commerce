"""Shop attribution and authorized printing of existing ERPNext invoices.

This module never creates sales, changes totals or changes the legal supplier.
"""
import re
import frappe
from local_commerce.permissions.scope import require_shop
from local_commerce.services.owner import reject


PRINT_FORMAT = 'Local dot Shop Invoice'


def attribute_invoice(doc, method=None):
    if doc.docstatus == 2:
        return
    previous = doc.get_doc_before_save()
    if previous and previous.docstatus == 1:
        for field in ('lc_shop', 'lc_shop_name'):
            if previous.get(field) != doc.get(field):
                reject('Submitted invoice shop attribution cannot be changed')
        return
    if doc.get('is_return') and doc.get('return_against'):
        original = frappe.get_doc('Sales Invoice', doc.return_against)
        if original.company != doc.company or original.customer != doc.customer:
            reject('Return supplier and customer must match the original invoice')
        doc.lc_shop, doc.lc_shop_name = original.get('lc_shop'), original.get('lc_shop_name')
        return
    if not doc.get('lc_order'):
        # Do not allow an unrelated native invoice to claim a marketplace shop.
        if doc.get('lc_shop') or doc.get('lc_shop_name'):
            reject('Shop attribution requires a linked Local Commerce order')
        return
    order = frappe.get_doc('LC Order', doc.lc_order)
    sales_order = frappe.get_doc('Sales Order', order.sales_order)
    if doc.company != sales_order.company or doc.customer != sales_order.customer:
        reject('Invoice supplier and customer must match the linked order')
    if any(row.get('sales_order') != sales_order.name for row in doc.items):
        reject('Invoice items must belong to the linked order')
    shop = frappe.get_doc('LC Shop', order.shop)
    doc.lc_shop = shop.name
    # Preserve the first saved name if the shop is renamed before submission.
    doc.lc_shop_name = (previous.get('lc_shop_name') if previous and previous.get('lc_shop') == shop.name else None) or shop.shop_name


def invoice_for_order(order):
    if frappe.session.user == 'Guest':
        frappe.throw('Sign in to download an invoice', frappe.PermissionError)
    doc = frappe.get_doc('LC Order', order)
    if doc.customer_user != frappe.session.user:
        require_shop(doc.shop)
    if not doc.sales_invoice:
        reject('The invoice has not been issued yet')
    invoice = frappe.get_doc('Sales Invoice', doc.sales_invoice)
    if invoice.docstatus != 1 or invoice.get('is_return'):
        reject('A submitted product invoice is not available for this order')
    if invoice.get('lc_order') != doc.name or (invoice.get('lc_shop') and invoice.lc_shop != doc.shop):
        reject('Invoice and shop references do not match; contact the administrator')
    so = frappe.get_doc('Sales Order', doc.sales_order)
    if invoice.company != so.company or invoice.customer != so.customer:
        reject('Invoice supplier and customer do not match the order')
    return doc, invoice


def download(order):
    doc, invoice = invoice_for_order(order)
    # Legacy invoices have no saved brand; add it only to this in-memory print copy.
    if not invoice.get('lc_shop_name'):
        invoice.lc_shop_name = frappe.db.get_value('LC Shop', doc.shop, 'shop_name')
    previous = frappe.flags.get('ignore_print_permissions')
    try:
        # Access was checked against this exact order above, never against Company alone.
        frappe.flags.ignore_print_permissions = True
        data = frappe.get_print('Sales Invoice', invoice.name, print_format=PRINT_FORMAT,
                                doc=invoice, as_pdf=True, no_letterhead=1)
    finally:
        frappe.flags.ignore_print_permissions = previous
    filename = re.sub(r'[^A-Za-z0-9_-]+', '-', str(invoice.lc_shop_name or 'shop')).strip('-')[:70] or 'shop'
    number = re.sub(r'[^A-Za-z0-9_-]+', '-', invoice.name)
    frappe.local.response.update(type='pdf', filename=f'{filename}-{number}.pdf', filecontent=data)


def listing(shop, start=0):
    require_shop(shop)
    start = int(start)
    if start < 0:
        reject('Invalid invoice page')
    # Join through the immutable order link so older invoices need no ledger rewrite.
    return frappe.db.sql('''select si.name, si.posting_date, si.customer_name,
        si.currency, si.grand_total, si.outstanding_amount, si.docstatus, o.name as order_id
        from `tabSales Invoice` si inner join `tabLC Order` o on o.name=si.lc_order
        where o.shop=%s and si.name=o.sales_invoice and si.is_return=0
        order by si.posting_date desc, si.name desc limit 20 offset %s''', (shop, start), as_dict=True)
