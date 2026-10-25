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
    if source not in ('', PERSONAL, ADJUSTMENT, 'Shop cash or bank', 'Supplier credit'):
        frappe.throw('Choose personal funds, shop cash/bank, supplier credit or a stock count adjustment.')
    if source and action != 'Add':
        frappe.throw('Purchase funding applies only when adding stock')


def funding_account(shop):
    account = frappe.db.get_value('Account', dict(company=shop.company,
        account_name=account_label(shop), root_type='Liability', is_group=0,
        disabled=0, account_currency='INR', account_type=''), 'name')
    if not account:
        frappe.throw('Ask the administrator to complete Local dot Setup/account provisioning before recording personally funded purchases.')
    return account


def post(shop, entry, source, payment_account="", supplier=""):
    if source not in (PERSONAL, 'Shop cash or bank', 'Supplier credit'):
        return None
    if not frappe.db.get_value('Company', shop.company, 'enable_perpetual_inventory'):
        frappe.throw('Enable perpetual inventory for this Company before recording shop stock purchases.')
    # Use submitted stock valuation, including ERPNext currency precision.
    amount = Decimal(str(entry.total_incoming_value or 0))
    if amount <= 0 or entry.docstatus != 1 or entry.company != shop.company:
        frappe.throw('A submitted positive stock receipt in this company is required')
    credit = purchase_credit(shop, source, payment_account, supplier)
    journal = frappe.get_doc(dict(doctype='Journal Entry', voucher_type='Journal Entry',
        company=shop.company, posting_date=entry.posting_date,
        user_remark=f'Shop purchase: {entry.name}; shop {shop.name}; payment source {source}; recorded by {frappe.session.user}.',
        accounts=[dict(account=shop.stock_adjustment_account,
                       debit_in_account_currency=float(amount), cost_center=shop.cost_center),
                  dict(**credit, credit_in_account_currency=float(amount),
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


def purchase_options(shop):
    from local_commerce.services.owner import shop_doc
    doc = shop_doc(shop, True)
    return dict(accounts=frappe.get_all('Account', filters=dict(company=doc.company,
        root_type='Asset', account_type=['in', ['Cash', 'Bank']], is_group=0,
        disabled=0, account_currency='INR'), fields=['name', 'account_type'],
        limit_page_length=500), suppliers=frappe.get_all('Supplier',
        filters=dict(lc_purchase_shop=shop, disabled=0), fields=['name', 'supplier_name'],
        limit_page_length=500))


def add_supplier(shop, supplier_name):
    from local_commerce.services.owner import shop_doc
    import hashlib
    shop_doc(shop, True)
    name = (supplier_name or '').strip()
    if not 2 <= len(name) <= 140:
        frappe.throw('Enter a supplier name between 2 and 140 characters')
    # The shop lock serializes retries; a supplied name never grants access to another shop's supplier.
    existing = frappe.db.get_value('Supplier', dict(lc_purchase_shop=shop, supplier_name=name), 'name')
    if existing:
        return existing
    group = frappe.db.get_value('Supplier Group', {'is_group': 0}, 'name')
    if not group:
        frappe.throw('Ask the administrator to configure a Supplier Group first')
    supplier = frappe.get_doc(dict(doctype='Supplier', supplier_name=name,
        supplier_type='Company', supplier_group=group, lc_purchase_shop=shop))
    supplier.insert(ignore_permissions=True, set_name='LC-SUP-' + hashlib.sha256(
        f'{shop}:{name}'.encode()).hexdigest()[:24])
    return supplier.name


def purchase_credit(shop, source, payment_account='', supplier=''):
    if source == PERSONAL:
        return dict(account=funding_account(shop))
    if source == 'Shop cash or bank':
        if not frappe.db.exists('Account', dict(name=payment_account, company=shop.company,
                root_type='Asset', account_type=['in', ['Cash', 'Bank']], is_group=0,
                disabled=0, account_currency='INR')):
            frappe.throw('Select an active INR cash or bank ledger belonging to this shop Company')
        return dict(account=payment_account)
    if source == 'Supplier credit':
        if not frappe.db.exists('Supplier', dict(name=supplier, lc_purchase_shop=shop.name, disabled=0)):
            frappe.throw('Select a supplier added for this shop')
        account = frappe.db.get_value('Company', shop.company, 'default_payable_account')
        if not account or not frappe.db.exists('Account', dict(name=account,
                company=shop.company, account_type='Payable', root_type='Liability',
                account_currency='INR', disabled=0, is_group=0)):
            frappe.throw('Ask the administrator to configure an active INR default Payable account for this Company')
        return dict(account=account, party_type='Supplier', party=supplier)
    frappe.throw('Choose a purchase payment source')
