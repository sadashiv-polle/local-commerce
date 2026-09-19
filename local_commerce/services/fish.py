"""Fish-shop lot expiry, reservations, market-price history and native stock postings."""

import hashlib
import json
from contextvars import ContextVar
from decimal import Decimal

import frappe
from frappe.utils import get_datetime, now_datetime

from local_commerce.permissions.scope import require_shop
from local_commerce.services import fish_rules
from local_commerce.services.owner import balance, checked_number, company_link, own_item, reject

_operation = ContextVar('lc_fish_operation', default=False)
_metadata = ContextVar('lc_fish_metadata', default={})
ACTIVE = ['Requested', 'Accepted', 'Preparing', 'Ready']


def enabled(shop, item=None):
    return shop.get('shop_type') == 'Fish' and (item is None or item.stock_uom in {'Kg', 'Nos'})


def require_fish(shop, item=None):
    if not enabled(shop, item):
        reject('This feature is only available for Kg or Nos products in Fish shops')


def selling_options(shop, item, rows):
    if enabled(shop, item) and item.stock_uom == 'Kg' and not rows:
        # Default fish option is a pre-weighed one-kilogram pack.
        return [{'id': 'fish-weight', 'label': '1 kg', 'kind': 'Weight', 'quantity': 1,
                 'estimated_weight': 1, 'billing': 'Weight', 'enabled': True}]
    return rows


def lots(shop, item=None):
    filters = {'shop': shop.name, 'warehouse': shop.warehouse, 'remaining': ['>', 0]}
    if item:
        filters['item'] = item
    rows = frappe.get_all('LC Fish Lot', filters=filters,
                          fields=['name', 'item', 'quantity', 'remaining', 'expires_at',
                                  'unit_cost', 'stock_entry', 'opening', 'creation'],
                          order_by='expires_at asc, name asc', limit_page_length=0)
    for row in rows:
        row.expires_at = get_datetime(row.expires_at)
    return rows


def reservations(shop, exclude_order=None):
    rows = frappe.get_all('LC Order', filters={'shop': shop.name, 'status': ['in', ACTIVE]},
                          fields=['name', 'fish_allocations_json'], limit_page_length=0)
    result = {}
    for row in rows:
        if row.name == exclude_order:
            continue
        for part in json.loads(row.fish_allocations_json or '[]'):
            result[part['lot']] = (result.get(part['lot'], Decimal(0))
                                   + Decimal(str(part['quantity'])))
    return result


def sellable(shop, item, native_available):
    if not enabled(shop, item):
        return native_available
    held = reservations(shop)
    now = now_datetime()
    valid = sum(max(Decimal(0), Decimal(str(row.remaining)) - held.get(row.name, 0))
                for row in lots(shop, item.name) if row.expires_at > now)
    return max(0, min(float(valid), float(native_available)))


def reserve(order, rows):
    shop = frappe.get_doc('LC Shop', order.shop)
    if not enabled(shop):
        return
    held = reservations(shop, exclude_order=order.name)
    parts = []
    totals = {}
    for row in rows:
        if frappe.db.get_value('Item', row.item_code, 'stock_uom') in {'Kg', 'Nos'}:
            totals[row.item_code] = (totals.get(row.item_code, Decimal(0))
                                    + Decimal(str(row.stock_qty)))
    for item, quantity in sorted(totals.items()):
        try:
            parts.extend(fish_rules.allocate(lots(shop, item), quantity, held, now_datetime()))
        except ValueError as exc:
            reject(str(exc))
    order.fish_allocations_json = json.dumps(parts)


def validate_order(order):
    shop = frappe.get_doc('LC Shop', order.shop)
    if not enabled(shop):
        return
    rows = json.loads(order.get('fish_allocations_json') or '[]')
    so = frappe.get_doc('Sales Order', order.sales_order)
    expected = {}
    for row in so.items:
        if row.stock_uom in {'Kg', 'Nos'}:
            expected[row.item_code] = (expected.get(row.item_code, Decimal(0))
                                      + Decimal(str(row.stock_qty)))
    actual = {}
    for part in rows:
        lot = frappe.get_doc('LC Fish Lot', part['lot'])
        if (lot.shop != shop.name or lot.warehouse != shop.warehouse or lot.item != part['item']
                or get_datetime(lot.expires_at) <= now_datetime()):
            reject('Reserved fish stock expired. Repack with fresh stock or cancel the order')
        actual[part['item']] = actual.get(part['item'], Decimal(0)) + Decimal(str(part['quantity']))
        if Decimal(str(part['quantity'])) > Decimal(str(lot.remaining)):
            reject('Reserved fish stock is no longer available')
    if expected != actual:
        reject('Fish stock allocation is missing. Cancel and place this order again')


def record(data):
    token = _operation.set(True)
    try:
        return frappe.get_doc(data).insert(ignore_permissions=True, set_name=data.get('name'))
    finally:
        _operation.reset(token)


def movement(shop, part, kind, stock_entry=None, delivery_note=None, order=None, reason=''):
    return record({'doctype': 'LC Fish Movement', 'shop': shop.name, 'warehouse': shop.warehouse,
                   'item': part['item'], 'lot': part['lot'], 'quantity': part['quantity'],
                   'kind': kind, 'stock_entry': stock_entry, 'delivery_note': delivery_note,
                   'order': order, 'reason': reason})


def consume(shop, parts, kind, **links):
    token = _operation.set(True)
    try:
        for part in parts:
            lot = frappe.get_doc('LC Fish Lot', part['lot'])
            remaining = Decimal(str(lot.remaining)) - Decimal(str(part['quantity']))
            if remaining < 0:
                reject('Fish stock changed; refresh before recording this movement')
            lot.remaining = float(remaining)
            lot.save(ignore_permissions=True)
            movement(shop, part, kind, **links)
    finally:
        _operation.reset(token)


def picked_up(order, note):
    shop = frappe.get_doc('LC Shop', order.shop)
    if enabled(shop):
        validate_order(order)
        parts = json.loads(order.get('fish_allocations_json') or '[]')
        allocated, dispatched = {}, {}
        for part in parts:
            allocated[part['item']] = (allocated.get(part['item'], Decimal(0))
                                       + Decimal(str(part['quantity'])))
        for row in note.items:
            if row.stock_uom in {'Kg', 'Nos'}:
                dispatched[row.item_code] = (dispatched.get(row.item_code, Decimal(0))
                                             + Decimal(str(row.stock_qty)))
        if allocated != dispatched:
            reject('ERPNext dispatched quantities differ from the fish stock allocation')
        consume(shop, parts, 'Sale',
                delivery_note=note.name, order=order.name, reason='Dispatched to customer')
        order.fish_allocations_json = '[]'


def price_changed(shop, item, previous):
    if not enabled(shop, item):
        return
    from local_commerce.services.owner import get_price

    price = get_price(shop, item)
    current = {'price': float(price.price_list_rate) if price else None,
               'options': json.loads(item.get('lc_selling_options') or '[]'),
               'hours': float(item.get('lc_stock_validity_hours') or 0)}
    if current != previous:
        record({'doctype': 'LC Fish Price Change', 'shop': shop.name, 'item': item.name,
                'weight_price': current['price'],
                'selling_options_json': json.dumps(current['options']),
                'validity_hours': current['hours']})


def adjust(shop, item, action, quantity, reason, request_key, unit_cost=0,
           validity_hours=None, lot=None):
    from local_commerce.services import owner

    shop_doc, product = own_item(shop, item, True)
    require_fish(shop_doc, product)
    if product.stock_uom == 'Nos':
        qty = checked_number(quantity, 'Number of pieces', positive=True)
        if qty != qty.to_integral_value():
            reject('Enter a whole number of pieces')
    if action not in {'Add', 'Remove', 'Wastage'}:
        reject('Choose Add, Remove or Wastage')
    metadata = {'kind': action, 'lot': lot or '', 'validity_hours': str(validity_hours or '')}
    token = _operation.set(True)
    meta_token = _metadata.set(metadata)
    frappe.db.savepoint('lc_fish_adjust')
    try:
        request_id = hashlib.sha256(
            f'{frappe.session.user}:{shop}:{request_key}'.encode()).hexdigest()
        replay = frappe.db.exists('LC Stock Operation', request_id)
        expires = None
        parts = []
        if not replay:
            if action == 'Add':
                try:
                    expires = fish_rules.expiry(now_datetime(), validity_hours)
                except ValueError as exc:
                    reject(str(exc))
            elif action == 'Wastage':
                selected = next((row for row in lots(shop_doc, item) if row.name == lot), None)
                if not selected or selected.expires_at > now_datetime():
                    reject('Select an expired stock lot from this fish shop')
                qty = checked_number(quantity, 'Wastage quantity', positive=True)
                free = Decimal(str(selected.remaining)) - reservations(shop_doc).get(lot, 0)
                if qty > free:
                    reject('This stock is reserved. Cancel or repack its orders before wastage')
                parts = [{'lot': lot, 'item': item, 'quantity': float(qty)}]
                company_link('Account', shop_doc.get('fish_wastage_account'), shop_doc.company,
                             {'is_group': 0, 'disabled': 0, 'root_type': 'Expense'})
                metadata['expense_account'] = shop_doc.fish_wastage_account
            else:
                try:
                    parts = fish_rules.allocate(lots(shop_doc, item), quantity,
                                                reservations(shop_doc), now_datetime())
                except ValueError as exc:
                    reject(str(exc))
        # Keep hash stable on wastage retries as well as first postings.
        if action == 'Wastage':
            metadata['expense_account'] = shop_doc.get('fish_wastage_account')
        result = owner.adjust_stock(shop, item, 'Add' if action == 'Add' else 'Remove',
                                    quantity, reason, request_key, unit_cost)
        if result['replayed']:
            return result
        if action == 'Add':
            stock_lot = record({'doctype': 'LC Fish Lot', 'shop': shop, 'item': item,
                                'warehouse': shop_doc.warehouse, 'quantity': float(quantity),
                                'remaining': float(quantity), 'unit_cost': float(unit_cost),
                                'expires_at': expires, 'validity_hours': float(validity_hours),
                                'stock_entry': result['stock_entry']})
            movement(shop_doc, {'lot': stock_lot.name, 'item': item, 'quantity': float(quantity)},
                     'Receipt', stock_entry=result['stock_entry'], reason=reason)
        else:
            consume(shop_doc, parts, action, stock_entry=result['stock_entry'], reason=reason)
        return result
    except Exception:
        frappe.db.rollback(save_point='lc_fish_adjust')
        raise
    finally:
        _metadata.reset(meta_token)
        _operation.reset(token)


def adopt(shop, item, validity_hours, request_key):
    shop_doc, product = own_item(shop, item, True)
    require_fish(shop_doc, product)
    if not isinstance(request_key, str) or not 16 <= len(request_key) <= 100:
        reject('A valid request key is required')
    identifier = hashlib.sha256(f'{shop}:{item}:{request_key}'.encode()).hexdigest()
    previous = frappe.db.get_value('LC Fish Lot', identifier,
                                   ['shop', 'item', 'validity_hours'], as_dict=True)
    if previous:
        if checked_number(validity_hours, 'Stock validity', positive=True) != checked_number(
            previous.validity_hours, 'Original stock validity'
        ):
            reject('This request key was already used with another stock validity period')
        return {'lot': identifier, 'replayed': True}
    stock = balance(item, shop_doc.warehouse, lock=True)
    tracked = sum(Decimal(str(row.remaining)) for row in lots(shop_doc, item))
    quantity = Decimal(str(stock['actual'])) - tracked
    if quantity <= 0:
        reject('No untracked stock remains')
    if stock['reserved']:
        reject('Finish or cancel existing orders before tracking existing fish stock')
    try:
        expires = fish_rules.expiry(now_datetime(), validity_hours)
    except ValueError as exc:
        reject(str(exc))
    rate = frappe.db.get_value('Bin', {'item_code': item, 'warehouse': shop_doc.warehouse},
                               'valuation_rate') or 0
    stock_lot = record({'doctype': 'LC Fish Lot', 'name': identifier, 'shop': shop, 'item': item,
                        'warehouse': shop_doc.warehouse, 'quantity': float(quantity),
                        'remaining': float(quantity), 'unit_cost': rate, 'opening': 1,
                        'expires_at': expires, 'validity_hours': float(validity_hours)})
    movement(shop_doc, {'lot': stock_lot.name, 'item': item, 'quantity': float(quantity)},
             'Opening', reason='Tracked existing warehouse stock; no stock receipt or GL posted')
    return {'lot': stock_lot.name, 'replayed': False}


def snapshot(shop):
    require_shop(shop, 'write')
    doc = frappe.get_doc('LC Shop', shop)
    require_fish(doc)
    held = reservations(doc)
    now = now_datetime()
    products = frappe.get_all('Item', filters={'lc_shop': shop, 'stock_uom': ['in', ['Kg', 'Nos']]},
                              fields=['name', 'item_name', 'disabled'], limit_page_length=0)
    from local_commerce.services.owner import detail

    items = [detail(shop, item.name) for item in products]
    stock_lots = lots(doc)
    for row in stock_lots:
        row['reserved'] = float(held.get(row.name, 0))
        row['free'] = max(0, row.remaining - row['reserved'])
        row['expired'] = row.expires_at <= now
    return {'items': items, 'lots': stock_lots,
            'currency': frappe.db.get_value('Company', doc.company, 'default_currency'),
            'wastage_account': doc.get('fish_wastage_account'),
            'price_history': frappe.get_all('LC Fish Price Change', filters={'shop': shop},
                                            fields=['name', 'item', 'creation', 'owner',
                                                    'weight_price', 'selling_options_json'],
                                            order_by='creation desc', limit_page_length=100),
            'movements': frappe.get_all('LC Fish Movement', filters={'shop': shop},
                                        fields=['name', 'item', 'lot', 'kind', 'quantity',
                                                'stock_entry', 'delivery_note', 'creation',
                                                'reason'],
                                        order_by='creation desc', limit_page_length=100)}


def protect_record(doc, method=None, **kwargs):
    if not _operation.get():
        frappe.throw('Use the Fish inventory workflow; these records are immutable',
                     frappe.PermissionError)


def protect_stock(doc, method=None, **kwargs):
    if _operation.get():
        return
    from local_commerce.services.orders import _order_operation

    for row in doc.get('items') or []:
        item = frappe.db.get_value('Item', row.item_code, ['lc_shop', 'stock_uom'], as_dict=True)
        if not item or item.stock_uom not in {'Kg', 'Nos'} or not item.lc_shop:
            continue
        if frappe.db.get_value('LC Shop', item.lc_shop, 'shop_type') != 'Fish':
            continue
        if doc.doctype == 'Delivery Note' and _order_operation.get() and doc.get('lc_order'):
            continue
        if doc.doctype == 'Sales Invoice' and not doc.get('update_stock'):
            continue
        reject('Use Fish inventory and orders to keep expiry, stock and wastage records consistent')


def protect_cancel(doc, method=None, **kwargs):
    for row in doc.get('items') or []:
        item = frappe.db.get_value('Item', row.item_code, ['lc_shop', 'stock_uom'], as_dict=True)
        if item and item.stock_uom in {'Kg', 'Nos'} and item.lc_shop and frappe.db.get_value(
            'LC Shop', item.lc_shop, 'shop_type'
        ) == 'Fish' and not (doc.doctype == 'Sales Invoice' and not doc.get('update_stock')):
            reject('Fish stock postings cannot be cancelled; use an opposite Fish stock movement')
