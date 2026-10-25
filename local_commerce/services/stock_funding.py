"""Explicit personal funding for inventory receipts; no supplier/GST bill invented."""
from decimal import Decimal
import frappe

PERSONAL = 'Personal funds'
ADJUSTMENT = 'Stock adjustment'


def account_label(shop):
    return 'LC Stock Funding Payable ' + shop.name


def provision(shop):
    from local_commerce.services.shop_onboarding import ensure_account
    return ensure_account(shop.company, account_label(shop), 'Liability', '')


def validate_source(action, source):
    if source not in ('', PERSONAL, ADJUSTMENT):
        frappe.throw('Choose personal funds or a stock count adjustment. Use ERPNext Purchasing for supplier credit or business-bank purchases.')
    if source and action != 'Add':
        frappe.throw('Purchase funding applies only when adding stock')


def funding_account(shop):
    account = frappe.db.get_value('Account', dict(company=shop.company,
        account_name=account_label(shop), root_type='Liability', is_group=0,
        disabled=0, account_currency='INR', account_type=''), 'name')
    if not account:
        frappe.throw('Ask the administrator to complete Local dot Setup/account provisioning before recording personally funded purchases.')
    return account


def post(shop, entry, source):
    if source != PERSONAL:
        return None
    if not frappe.db.get_value('Company', shop.company, 'enable_perpetual_inventory'):
        frappe.throw('Enable perpetual inventory for this Company before recording personally funded stock purchases.')
    # Use submitted stock valuation, including ERPNext currency precision.
    amount = Decimal(str(entry.total_incoming_value or 0))
    if amount <= 0 or entry.docstatus != 1 or entry.company != shop.company:
        frappe.throw('A submitted positive stock receipt in this company is required')
    journal = frappe.get_doc(dict(doctype='Journal Entry', voucher_type='Journal Entry',
        company=shop.company, posting_date=entry.posting_date,
        user_remark=f'Personally funded stock purchase: {entry.name}; shop {shop.name}. Funding supplied by shop owner; recorded by {frappe.session.user}.',
        accounts=[dict(account=shop.stock_adjustment_account,
                       debit_in_account_currency=float(amount), cost_center=shop.cost_center),
                  dict(account=funding_account(shop), credit_in_account_currency=float(amount),
                       cost_center=shop.cost_center)]))
    journal.flags.ignore_permissions = True
    journal.insert(ignore_permissions=True)
    journal.submit()
    return journal.name


def protect_journal(doc, method=None):
    if frappe.db.exists('LC Stock Operation', {'funding_journal': doc.name}):
        frappe.throw('This journal funds an app stock receipt. Use a reviewed reversal entry; its stock-operation history must remain intact.')


def validate_wastage(account):
    if account and frappe.db.get_value('Account', account, 'account_type') == 'Depreciation':
        frappe.throw('Choose a Fish Wastage expense account, not Depreciation. Ask the administrator to correct the shop wastage setting.')
