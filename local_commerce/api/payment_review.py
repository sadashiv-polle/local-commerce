"""Shop-scoped review queues; payment mutations use existing verified workflows."""
import frappe

from local_commerce.permissions.scope import require_shop
from local_commerce.services.orders import offset, serialize
from local_commerce.services.owner import reject


@frappe.whitelist(methods=['GET'])
def list_orders(shop, category='upi', start=0):
    require_shop(shop, 'write')
    filters = {'shop': shop}
    if category == 'upi':
        filters.update(payment_method='Manual UPI', payment_status='Awaiting Verification')
    elif category == 'cashfree':
        filters.update(payment_method='Cashfree', payment_status=['in', ['Pending', 'Failed']],
                       status=['not in', ['Cancelled', 'Delivered']])
    elif category == 'accounting':
        filters.update(payment_method='Cashfree', gateway_accounting_error=['is', 'set'])
    elif category == 'refunds':
        filters.update(payment_method='Cashfree', gateway_refunded_amount=['>', 0])
    else:
        reject('Choose a valid payment review category')
    names = frappe.get_all('LC Order', filters=filters, pluck='name',
                           order_by='creation asc', start=offset(start), limit_page_length=21)
    return {'orders': [serialize(frappe.get_doc('LC Order', name)) for name in names[:20]],
            'has_more': len(names) > 20}
