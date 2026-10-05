"""Atomically replace expired order reservations and post the released stock as wastage."""
import hashlib
import json
from decimal import Decimal

import frappe
from frappe.utils import get_datetime, now_datetime

from local_commerce.services import fish


def recover(order):
    from local_commerce.services.orders import _order_operation

    doc = frappe.get_doc('LC Order', order)
    frappe.db.sql('select name from `tabLC Shop` where name=%s for update', doc.shop)
    frappe.db.sql('select name from `tabLC Order` where name=%s for update', doc.name)
    doc.reload()
    if doc.status not in fish.ACTIVE or doc.payment_status == 'Refunded' or doc.get('gateway_refunded_amount'):
        return False
    shop = frappe.get_doc('LC Shop', doc.shop)
    if not fish.enabled(shop):
        return False
    expired = {}
    for part in json.loads(doc.fish_allocations_json or '[]'):
        lot = frappe.get_doc('LC Fish Lot', part['lot'])
        if get_datetime(lot.expires_at) <= now_datetime():
            key = (part['lot'], part['item'])
            expired[key] = expired.get(key, Decimal(0)) + Decimal(str(part['quantity']))
    if not expired:
        return False
    # Uses the original Sales Order quantities and items; respects other orders
    # and the scheduled delivery cutoff. Insufficient stock aborts this transaction.
    fish.validate_order(doc, refresh_expired=True)
    token = _order_operation.set(True)
    try:
        # A previously packed order must be physically repacked before dispatch.
        if doc.status == 'Ready':
            doc.status = 'Preparing'
        doc.save(ignore_permissions=True)
        for (lot, item), quantity in sorted(expired.items()):
            key = hashlib.sha256(f'expiry-recovery:{doc.name}:{lot}'.encode()).hexdigest()
            fish.adjust(doc.shop, item, 'Wastage', float(quantity),
                        'Expired reservation replaced for order ' + doc.name, key, lot=lot)
        doc.add_comment('Info', 'Expired reserved stock posted as wastage and replaced with fresh stock of the same items. Physically repack before marking Ready.')
    finally:
        _order_operation.reset(token)
    return True


def process_pending():
    previous_user = frappe.session.user
    try:
        frappe.set_user('Administrator')
        # Only shops with expired stock need an order scan.
        shops = frappe.get_all('LC Fish Lot', filters={'remaining': ['>', 0],
            'expires_at': ['<=', now_datetime()]}, pluck='shop', distinct=True)
        for shop in shops:
            orders = frappe.get_all('LC Order', filters={'shop': shop, 'status': ['in', fish.ACTIVE]},
                                    pluck='name', order_by='creation asc', limit_page_length=0)
            for order in orders:
                try:
                    recover(order)
                    frappe.db.commit()
                except Exception:
                    frappe.db.rollback()
                    frappe.log_error(title='Stock expiry recovery', message=frappe.get_traceback())
    finally:
        frappe.set_user(previous_user)
