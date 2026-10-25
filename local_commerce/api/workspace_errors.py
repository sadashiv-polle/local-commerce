"""Expose bounded validation text only after checking shop workspace access."""
from functools import wraps
import frappe
from frappe.utils import strip_html
from local_commerce.permissions.scope import require_shop


def workspace_validation(function):
    @wraps(function)
    def wrapped(shop, *args, **kwargs):
        require_shop(shop, 'write')
        try:
            return function(shop, *args, **kwargs)
        except frappe.ValidationError as exc:
            if not frappe.local.response.get('lc_message'):
                detail = strip_html(str(exc)).strip()[:1800]
                frappe.local.response['lc_message'] = 'Shop workspace: ' + (
                    detail or 'Review the product, warehouse and accounting settings.')
            # Preserve transaction rollback; never convert posting failures to success.
            raise
    return wrapped
