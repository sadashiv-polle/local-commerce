"""Transactional, platform-authorized setup of a shop's accounting resources."""
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject


# Stable names allow reuse within a Company without changing its existing ledgers.
ACCOUNTS = {
    'cashfree_commission_account': ('LC Commission on Sales', 'Expense', ''),
    'gst_shop_payable': ('LC Amounts Payable to Platform', 'Liability', ''),
    'gst_shop_eco_account': ('LC Restaurant GST Collected for ECO', 'Liability', 'Tax'),
    'cashfree_clearing_account': ('LC Cashfree Clearing', 'Asset', 'Bank'),
    'cashfree_bank_account': ('LC Shop Bank', 'Asset', 'Bank'),
    'cashfree_fee_account': ('LC Gateway Charges', 'Expense', ''),
    'cashfree_fee_tax_account': ('LC Gateway Fee GST Expense', 'Expense', ''),
    'cod_cash_account': ('LC Cash', 'Asset', 'Cash'),
    'delivery_account': ('LC Delivery Income', 'Income', ''),
    'stock_adjustment_account': ('LC Stock Adjustment', 'Expense', 'Stock Adjustment'),
    'fish_wastage_account': ('LC Fish Wastage', 'Expense', ''),
}


def ensure_account(company, label, root, kind):
    filters = dict(company=company, account_name=label)
    name = frappe.db.get_value('Account', filters, 'name')
    if name:
        account = frappe.get_doc('Account', name)
        if (account.root_type != root or account.is_group or account.disabled
                or account.account_currency != 'INR' or (account.account_type or '') != kind):
            reject(f'Existing account {name} is incompatible. Review it before automatic setup')
        return name
    parent = frappe.db.get_value('Account', dict(company=company, root_type=root,
        is_group=1, disabled=0, parent_account=['in', ['', None]]), 'name')
    if not parent:
        # Standard ERPNext root ledgers can have SQL NULL parent_account.
        parents = frappe.get_all('Account', filters=dict(company=company,root_type=root,is_group=1,disabled=0),
            fields=['name','parent_account'], order_by='lft asc')
        parent = next((r.name for r in parents if not r.parent_account), None)
    if not parent:
        reject(f'No active {root} root account exists in {company}')
    return frappe.get_doc(dict(doctype='Account', account_name=label, company=company,
        parent_account=parent, is_group=0, account_currency='INR', account_type=kind)).insert(ignore_permissions=True).name


def payment_mode(name, kind):
    if frappe.db.exists('Mode of Payment', name):
        if frappe.db.get_value('Mode of Payment', name, 'type') != kind:
            reject(f'Mode of Payment {name} must have type {kind}')
    else:
        frappe.get_doc(dict(doctype='Mode of Payment',mode_of_payment=name,type=kind,enabled=1)).insert(ignore_permissions=True)
    return name


def provision(shop, bank_details=None):
    require_platform()
    # Serialize provisioning for shops sharing a Company; the request transaction owns this lock.
    company = frappe.get_doc('Company', shop.company, for_update=True)
    if company.default_currency != 'INR':
        reject('Automatic marketplace account setup currently requires an INR Company')
    from local_commerce.services.shop_banking import configure as configure_bank
    selected_bank = configure_bank(shop, bank_details)
    for field, (label, root, kind) in ACCOUNTS.items():
        if field == "cashfree_bank_account" and selected_bank:
            continue
        if field == 'fish_wastage_account' and shop.shop_type != 'Fish':
            continue
        shop.set(field, ensure_account(shop.company,label,root,kind))
    shop.upi_bank_account = shop.cashfree_bank_account
    shop.cod_mode_of_payment = payment_mode('Cash', 'Cash')
    shop.upi_mode_of_payment = payment_mode('UPI', 'Bank')
    shop.cashfree_mode_of_payment = payment_mode('Cashfree', 'Bank')
    shop.cashfree_commission_type = 'Percentage'
    shop.cashfree_commission = 0 if shop.get('business_model') == 'Owned shop' else shop.gst_commission_rate
    cost_center = company.cost_center
    if not cost_center or not frappe.db.exists('Cost Center',dict(name=cost_center,company=shop.company,is_group=0,disabled=0)):
        reject('Set an active non-group default Cost Center on the Company before automatic setup')
    if shop.get('business_model') == 'Owned shop':
        root = frappe.db.get_value('Cost Center', dict(company=shop.company, is_group=1,
            disabled=0), 'name')
        if not root:
            reject('Create an active group Cost Center for the legal Company first')
        cc_label = 'LC Shop ' + shop.name
        owned_cc = frappe.db.get_value('Cost Center', dict(company=shop.company,
            cost_center_name=cc_label), 'name')
        if owned_cc:
            if not frappe.db.exists('Cost Center', dict(name=owned_cc, company=shop.company,
                    is_group=0, disabled=0)):
                reject('The shop Cost Center must be an active non-group Cost Center')
        else:
            owned_cc = frappe.get_doc(dict(doctype='Cost Center', company=shop.company,
                cost_center_name=cc_label, parent_cost_center=root, is_group=0)).insert(ignore_permissions=True).name
        cost_center = owned_cc
    # Each shop gets a dedicated warehouse, even when several shops share a Company.
    label = 'LC Shop ' + shop.name
    warehouse = frappe.db.get_value('Warehouse',dict(company=shop.company,warehouse_name=label),'name')
    if warehouse:
        if not frappe.db.exists('Warehouse',dict(name=warehouse,company=shop.company,is_group=0,disabled=0)):
            reject('The existing shop warehouse is disabled or a group')
    else:
        warehouse = frappe.get_doc(dict(doctype='Warehouse',warehouse_name=label,
            company=shop.company,is_group=0)).insert(ignore_permissions=True).name
    shop.warehouse, shop.cost_center = warehouse, cost_center
    # Leave all payment methods, GST and storefront ordering inactive for review.
    shop.cod_enabled = shop.upi_enabled = shop.cashfree_enabled = shop.gst_enabled = 0
    shop.accepting_orders = 0
    shop.save()
    from local_commerce.services.owner import configure
    configure(shop.name,warehouse,shop.stock_adjustment_account,cost_center)


def apply_details(shop, values):
    from local_commerce.services.payments.rules import money
    from local_commerce.services.gst.rules import MODES
    values = frappe.parse_json(values) if values else {}
    allowed = {'legal_name', 'address', 'city', 'postal_code', 'state', 'shop_type', 'gst_mode', 'commission'}
    if not isinstance(values, dict) or set(values) - allowed:
        reject('Invalid shop setup details')
    for key in ('legal_name','address','city','postal_code','state'):
        value = str(values.get(key) or '').strip()
        if not value or len(value) > (1000 if key == 'address' else 140):
            reject('Enter the legal name, address, city, postal code and GST state code')
        values[key] = value
    state = values['state']
    if len(state) != 2 or not state.isascii() or not state.isdigit() or not 1 <= int(state) <= 38:
        reject('Enter a valid two-digit GST state code')
    if shop.gst_number and shop.gst_number[:2] != state:
        reject('Shop state and GSTIN state must match')
    if values.get('shop_type') not in ('General','Fish') or values.get('gst_mode') not in MODES:
        reject('Choose a shop type and intended GST treatment')
    if values['gst_mode'] == 'Seller GST' and shop.gst_registration != 'Registered':
        reject('Seller GST requires a registered shop')
    try:
        rate = money(values.get('commission',7))
        if not 0 < rate < 100:
            raise ValueError()
    except ValueError:
        reject('Commission must be greater than zero and below 100')
    shop.update(dict(gst_legal_name=values['legal_name'],gst_address=values['address'],
        gst_state=state,address_line1=values['address'],city=values['city'],postal_code=values['postal_code'],
        shop_type=values['shop_type'],gst_mode=values['gst_mode'],gst_commission_rate=float(rate),
        gst_commission_inclusive=1))
