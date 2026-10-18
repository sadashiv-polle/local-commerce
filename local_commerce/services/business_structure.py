"""Guard business identity while the legacy multi-company ledger is retained."""
import frappe
from local_commerce.permissions.scope import require_platform


def validate_shop_structure(shop):
    model = shop.get('business_model') or 'Legacy'
    previous = shop.get_doc_before_save()
    if model not in ('Legacy', 'Owned shop', 'Third-party vendor'):
        frappe.throw('Choose a valid business model')
    if previous and (previous.get('business_model') or 'Legacy') != model:
        require_platform()
        if (frappe.db.exists('LC Order', {'shop': shop.name})
                or frappe.db.exists('Item', {'lc_shop': shop.name})):
            frappe.throw('A shop with products or orders needs an accounting migration before changing its business model')
    if model == 'Third-party vendor':
        frappe.throw('Single-company vendor accounting is not available yet; do not post vendor sales through the retail flow')
    if model == 'Owned shop':
        if shop.get('gst_enabled'):
            frappe.throw('Owned shops use product tax templates, not marketplace commission GST')
        if float(shop.get('cashfree_commission') or 0):
            frappe.throw('Do not charge marketplace commission to your own shop')
        if shop.get('cashfree_settlement_mode') == 'Easy Split':
            frappe.throw('Use Direct merchant settlement for your own shop')
