import json
import re
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject
from .rules import MODES, gstin
from local_commerce.services.payments.rules import money

SHOP_FIELDS = ('gst_enabled', 'gst_mode', 'gst_registration', 'gst_legal_name', 'gst_number',
               'gst_state', 'gst_address', 'gst_commission_rate', 'gst_commission_inclusive',
               'gst_shop_payable', 'gst_shop_eco_account', 'cashfree_commission_account',
               'commission_customer', 'commission_prepaid')
PLATFORM_FIELDS = ('gst_company', 'gst_legal_name', 'gst_number', 'gst_state', 'gst_address',
    'gst_sac', 'gst_rate', 'gst_cost_center', 'gst_clearing', 'gst_receivable', 'gst_income',
    'gst_cgst', 'gst_sgst', 'gst_igst', 'gst_eco_cgst', 'gst_eco_sgst', 'gst_eco_igst',
    'gst_bank', 'gst_fee', 'gst_fee_tax', 'commission_billing_enabled',
    'commission_receivable', 'commission_deferred', 'commission_item', 'commission_due_days', 'commission_reminders')


def active(shop):
    return bool(shop.get('gst_enabled'))


def identity(values, prefix='gst_'):
    if not values.get(prefix+'legal_name') or not values.get(prefix+'address'):
        reject('Enter the legal name and complete billing address')
    state = str(values.get(prefix+'state') or '')
    if not re.fullmatch(r'\d{2}', state) or not 1 <= int(state) <= 38:
        reject('Enter a two-digit Indian GST state code')
    number = values.get(prefix+'number') or ''
    if number:
        try:
            number = gstin(number)
        except ValueError as exc:
            reject(str(exc))
        if number[:2] != state:
            reject('GSTIN and state code do not match')
    return dict(legal_name=values.get(prefix+'legal_name'), address=values.get(prefix+'address'),
                state=state, gstin=number)


def account(name, company, root, bank=False):
    row = frappe.db.get_value('Account', name,
        ['company','root_type','disabled','is_group','account_currency','account_type'], as_dict=True)
    if (not row or row.company != company or row.root_type != root or row.disabled or row.is_group
            or row.account_currency != 'INR' or (bank and row.account_type != 'Bank')
            or row.account_type in ('Receivable', 'Payable')):
        reject(f'Select an active INR {root} ledger in {company}; party-control accounts are not supported here')
    return name


def profile():
    settings = frappe.get_single('LC Store Settings')
    party = identity(settings)
    if not party['gstin']:
        reject('Add the platform GSTIN before enabling GST collection')
    company = settings.get('gst_company')
    if not company or frappe.db.get_value('Company', company, 'default_currency') != 'INR':
        reject('Select the platform INR Company')
    if not re.fullmatch(r'\d{6}', str(settings.get('gst_sac') or '')):
        reject('Enter the accountant-confirmed six-digit commission SAC')
    if money(settings.get('gst_rate') or 0) != 18:
        reject('This commission model supports 18% GST')
    cc = frappe.db.get_value('Cost Center', settings.get('gst_cost_center'), ['company','is_group'], as_dict=True)
    if not cc or cc.company != company or cc.is_group:
        reject('Select a platform cost center')
    accounts = {}
    for key, root in [('clearing','Asset'),('receivable','Asset'),('income','Income'),
            ('cgst','Liability'),('sgst','Liability'),('igst','Liability'),
            ('eco_cgst','Liability'),('eco_sgst','Liability'),('eco_igst','Liability'),
            ('bank','Asset'),('fee','Expense'),('fee_tax','Expense')]:
        accounts[key] = account(settings.get('gst_'+key), company, root, key in ('bank','clearing'))
    if len({accounts[k] for k in ('bank', 'clearing', 'receivable')}) != 3:
        reject('Use separate bank, gateway clearing and shop-receivable ledgers')
    if len({accounts[k] for k in ('cgst','sgst','igst','eco_cgst','eco_sgst','eco_igst')}) != 6:
        reject('Use separate commission and Section 9(5) tax ledgers for each tax head')
    return dict(company=company, party=party, sac=settings.gst_sac, rate='18.00',
                cost_center=settings.gst_cost_center, accounts=accounts)


def validate_shop(shop, method=None):
    previous = shop.get_doc_before_save()
    if method is not None and ((previous and any(previous.get(f) != shop.get(f) for f in SHOP_FIELDS)) or (
            not previous and active(shop))):
        require_platform()
    if not active(shop):
        return
    if shop.get('gst_mode') not in MODES[1:]:
        reject('Select the GST supply treatment before enabling')
    party = identity(shop)
    registration = shop.get('gst_registration')
    if registration not in ('Registered','Unregistered'):
        reject('Confirm whether the shop is registered or unregistered')
    if bool(party['gstin']) != (registration == 'Registered'):
        reject('Registered shops require a GSTIN; unregistered shops must not have one')
    if shop.gst_mode == 'Seller GST' and registration != 'Registered':
        reject('Seller-GST mode requires a registered seller')
    platform = profile()
    if frappe.db.get_value('Company', shop.company, 'default_currency') != 'INR':
        reject('Marketplace GST requires an INR shop Company')
    if platform['company'] == shop.company:
        reject('Commission invoices require a separate vendor Company. Keep your own shop in Legacy mode')
    if not 0 < money(shop.get('gst_commission_rate') or 0) < 100:
        reject('Enter a commission percentage greater than zero and below 100')
    account(shop.get('cashfree_commission_account'), shop.company, 'Expense')
    account(shop.get('gst_shop_payable'), shop.company, 'Liability')
    if shop.gst_mode == 'Restaurant 9(5)':
        account(shop.get('gst_shop_eco_account'), shop.company, 'Liability')
        if shop.order_tax_template:
            reject('Remove the seller tax template for Section 9(5); the app adds restaurant GST once')
    from .commission import billing_snapshot
    billing_snapshot(shop, platform)
    if shop.get('cashfree_enabled') and shop.get('cashfree_settlement_mode') != 'Easy Split':
        reject('Use Easy Split for a third-party shop with marketplace GST')


def snapshot(shop, so, payment_method):
    if not active(shop):
        return None
    from .rules import amounts
    validate_shop(shop)
    platform = profile()
    delivery = sum(money(t.tax_amount) for t in so.taxes if t.description == 'Delivery charge')
    base = money(so.net_total)
    tax = money(so.grand_total) - base - delivery
    if tax < 0:
        reject('Unsupported tax adjustment; review the order before collecting payment')
    try:
        values = amounts(base, delivery, tax, so.grand_total, shop.gst_commission_rate,
                         platform['rate'], bool(shop.gst_commission_inclusive), shop.gst_mode)
    except ValueError as exc:
        reject(str(exc))
    from .commission import billing_snapshot
    billing = billing_snapshot(shop, platform)
    return dict(version=2 if billing else 1, billing=billing, mode=shop.gst_mode, registration=shop.gst_registration,
        shop_party=identity(shop), platform=platform, amounts=values,
        commission_rate=str(money(shop.gst_commission_rate)),
        inclusive=bool(shop.gst_commission_inclusive), shop_company=shop.company,
        shop_cost_center=shop.cost_center, expense=shop.cashfree_commission_account,
        shop_payable=shop.gst_shop_payable, shop_eco=shop.get('gst_shop_eco_account'),
        payment_method=payment_method, fee_bearer='Platform')


def apply_tax(shop, so, delivery_fee):
    if not active(shop) or shop.get('gst_mode') != 'Restaurant 9(5)':
        return
    validate_shop(shop)
    if any(row.get('item_tax_template') for row in so.items):
        reject('Section 9(5) orders cannot mix item tax templates; use separate products/shops')
    if any(row.description != 'Delivery charge' for row in so.taxes):
        reject('Remove default seller taxes before enabling restaurant ECO tax')
    so.calculate_taxes_and_totals()
    tax = money((money(so.net_total) + money(delivery_fee)) * money('0.05'))
    so.append('taxes', dict(charge_type='Actual', account_head=shop.gst_shop_eco_account,
        description='Restaurant GST payable by ECO under Section 9(5)', tax_amount=float(tax)))
