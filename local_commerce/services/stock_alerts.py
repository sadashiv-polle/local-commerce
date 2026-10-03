"""One-shot restock subscriptions; availability uses the same rules as the storefront."""
import hashlib
from urllib.parse import quote

import frappe
from frappe.utils import now_datetime

from local_commerce.services.owner import reject


def user():
    if frappe.session.user == 'Guest':
        frappe.throw('Sign in to receive stock alerts', frappe.PermissionError)
    return frappe.session.user


def key(account, item):
    return hashlib.sha256(f'{account}\0{item}'.encode()).hexdigest()


def ids():
    return frappe.get_all('LC Stock Alert', filters={'user': user()}, pluck='item',
                          limit_page_length=200)


def toggle(shop, item, saved=1):
    from local_commerce.services.orders import public_product

    account = user()
    if not isinstance(item, str) or not isinstance(shop, str) or str(saved) not in ('0', '1'):
        reject('Invalid stock alert')
    frappe.db.sql('select name from `tabUser` where name=%s for update', (account,))
    name = key(account, item)
    exists = frappe.db.exists('LC Stock Alert', name)
    if str(saved) == '0':
        if exists:
            frappe.delete_doc('LC Stock Alert', name, ignore_permissions=True)
        return {'saved': False}
    product = public_product(shop, item)
    if product['available'] > 0:
        reject('This item is already in stock. Refresh the shop to order it.')
    if not exists:
        if frappe.db.count('LC Stock Alert', {'user': account}) >= 200:
            reject('You can follow up to 200 sold-out products')
        frappe.get_doc({'doctype': 'LC Stock Alert', 'name': name, 'user': account,
                        'shop': shop, 'item': item}).insert(ignore_permissions=True)
    return {'saved': True}


def restocked(product):
    if not product or product['available'] <= 0:
        return False
    options = product.get('selling_options') or []
    if options:
        return any(
            0 < float(option.get('estimated_weight') or 0) <= product['available']
            and (option.get('piece_price') is not None
                 if option.get('billing') == 'Pieces' else product.get('rate') is not None)
            for option in options
        )
    return product.get('rate') is not None


def notify(row, product):
    from local_commerce.services.notifications import _notification_operation

    token = _notification_operation.set(True)
    try:
        shop_name = frappe.db.get_value('LC Shop', row.shop, 'shop_name') or 'your shop'
        notification = frappe.get_doc({
            'doctype': 'LC Notification', 'recipient_user': row.user, 'shop': row.shop,
            'item': row.item, 'audience': 'Customer', 'title': 'Back in stock',
            'message': f'{product["item_name"]} is available again at {shop_name}. '
                       'Open the shop to check current stock and price.',
            'target': f'/store/{quote(row.shop, safe="")}?item={quote(row.item, safe="")}',
            'read': 0,
        }).insert(ignore_permissions=True)
        frappe.enqueue('local_commerce.services.push.send_notification',
                       notification=notification.name, enqueue_after_commit=True, queue='short')
    finally:
        _notification_operation.reset(token)


def process_one(name):
    from local_commerce.services.orders import public_product

    # Serialize scheduler overlap and cancellation. Notification + deletion commit together.
    rows = frappe.db.sql('select name from `tabLC Stock Alert` where name=%s for update', (name,))
    if not rows:
        return
    row = frappe.get_doc('LC Stock Alert', name)
    if not frappe.db.get_value('User', row.user, 'enabled'):
        frappe.delete_doc('LC Stock Alert', name, ignore_permissions=True)
        return
    try:
        product = public_product(row.shop, row.item)
    except (frappe.ValidationError, frappe.DoesNotExistError, frappe.PermissionError):
        product = None
    if restocked(product):
        notify(row, product)
        frappe.delete_doc('LC Stock Alert', name, ignore_permissions=True)
    else:
        frappe.db.set_value('LC Stock Alert', name, 'last_checked', now_datetime())


def process_pending():
    # Oldest checked first: a permanently sold-out item cannot starve later subscribers.
    names = frappe.get_all('LC Stock Alert', pluck='name', order_by='modified asc, name asc',
                           limit_page_length=200)
    for name in names:
        try:
            process_one(name)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title='Stock alert check failed', message=frappe.get_traceback())
            # Move a broken record to the back, allowing other subscriptions to proceed.
            if frappe.db.exists('LC Stock Alert', name):
                frappe.db.set_value('LC Stock Alert', name, 'last_checked', now_datetime())
                frappe.db.commit()
