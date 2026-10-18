"""Additive installation bootstrap. No tax registration or payment activation."""
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services.shop_onboarding import ensure_account
from local_commerce.services.owner import reject

COMPANY = 'Shiv Tech Works'
SHOP = 'Daily Basket'
PLATFORM_ACCOUNTS = {
    'gst_income': ('LC Marketplace Commission Income', 'Income', ''),
    'gst_receivable': ('LC Commission Receivable', 'Asset', ''),
    'gst_clearing': ('LC Marketplace Clearing', 'Asset', 'Bank'),
    'gst_fee': ('LC Gateway and Easy Split Charges', 'Expense', ''),
    'gst_fee_tax': ('LC Gateway Fee GST Expense', 'Expense', ''),
    'setup_vendor_payable': ('LC Vendor Settlements Payable', 'Liability', ''),
}
SHOP_ACCOUNTS = {
    'retail_income_account': ('LC Retail Sales', 'Income', ''),
    'stock_adjustment_account': ('LC Stock Adjustment', 'Expense', 'Stock Adjustment'),
    'fish_wastage_account': ('LC Fish Wastage', 'Expense', ''),
    'delivery_account': ('LC Delivery Income', 'Income', ''),
}


def _set_missing(doc, field, value):
    if not doc.get(field):
        doc.set(field, value)


def _ledger(doc, field, company, spec):
    if doc.get(field):
        if not frappe.db.exists('Account', dict(name=doc.get(field), company=company,
                root_type=spec[1], is_group=0, disabled=0, account_currency='INR')):
            reject(f'Review the existing {field} account; it was not changed')
        return
    doc.set(field, ensure_account(company, *spec))


def _centre(company, label, current=None):
    name = current or frappe.db.get_value('Cost Center', dict(company=company, cost_center_name=label), 'name')
    if name:
        if not frappe.db.exists('Cost Center', dict(name=name, company=company, is_group=0, disabled=0)):
            reject('Review the existing cost centre; it was not changed')
        return name
    parent = frappe.db.get_value('Cost Center', dict(company=company, is_group=1, disabled=0), 'name')
    if not parent:
        reject('Complete ERPNext Company setup to create its root cost centre, then retry')
    return frappe.get_doc(dict(doctype='Cost Center', cost_center_name=label,
        company=company, parent_cost_center=parent, is_group=0)).insert(ignore_permissions=True).name


def initialize(confirm_company='', confirm_shop=''):
    """One transaction, serialized even before singleton values exist. Admin only."""
    require_platform()
    frappe.db.sql('select name from `tabDocType` where name=%s for update', ('LC Store Settings',))
    settings = frappe.get_single('LC Store Settings')
    company_name = settings.gst_company
    if not company_name and frappe.db.exists('Company', COMPANY):
        if confirm_company != COMPANY:
            reject('Shiv Tech Works already exists. Confirm its identity in Local dot Setup before linking it')
        company_name = COMPANY
    if not company_name:
        abbr = 'STW'
        if frappe.db.exists('Company', {'abbr': abbr}):
            abbr = 'STW' + frappe.generate_hash(length=6).upper()
        company_name = frappe.get_doc(dict(doctype='Company', company_name=COMPANY,
            abbr=abbr, country='India', default_currency='INR',
            create_chart_of_accounts_based_on='Standard Template', chart_of_accounts='Standard'
        )).insert(ignore_permissions=True).name
    company = frappe.get_doc('Company', company_name, for_update=True)
    if company.country != 'India' or company.default_currency != 'INR':
        reject('The platform Company must use India and INR. Existing Company settings were not changed')
    _set_missing(settings, 'gst_company', company.name)
    _set_missing(settings, 'marketplace_name', 'Local dot')
    # Persist the Company link before LC Shop validates its ownership.
    settings.save(ignore_permissions=True)
    shop_name = settings.get('setup_shop')
    if not shop_name:
        matches = frappe.get_all('LC Shop', filters={'shop_name': SHOP}, pluck='name')
        if matches:
            if confirm_shop not in matches:
                reject('Daily Basket already exists. Select and confirm the intended owned shop in Local dot Setup')
            shop_name = confirm_shop
    if shop_name:
        shop = frappe.get_doc('LC Shop', shop_name, for_update=True)
        if shop.company != company.name or shop.business_model != 'Owned shop':
            reject('The selected shop must already be an Owned shop in the platform Company; no historical data was migrated')
    else:
        shop = frappe.get_doc(dict(doctype='LC Shop', shop_name=SHOP, company=company.name,
            company_country='India', company_currency='INR', business_model='Owned shop',
            shop_type='General', status='Draft', accepting_orders=0, cod_enabled=0,
            upi_enabled=0, cashfree_enabled=0, gst_enabled=0, gst_registration='Unverified',
            gst_commission_rate=0, cashfree_commission=0, cashfree_settlement_mode='Direct merchant'
        )).insert(ignore_permissions=True)
    for field, spec in PLATFORM_ACCOUNTS.items():
        _ledger(settings, field, company.name, spec)
    settings.gst_cost_center = _centre(company.name, 'Local dot Marketplace', settings.gst_cost_center)
    for field, spec in SHOP_ACCOUNTS.items():
        label, root, kind = spec
        # Stable shop key survives renames and distinguishes additional owned shops.
        _ledger(shop, field, company.name, (label + ' ' + shop.name, root, kind))
    shop.cost_center = _centre(company.name, 'LC Shop ' + shop.name, shop.cost_center)
    warehouse = shop.warehouse or frappe.db.get_value('Warehouse', dict(company=company.name,
        warehouse_name='LC Shop ' + shop.name), 'name')
    if warehouse:
        if not frappe.db.exists('Warehouse', dict(name=warehouse, company=company.name, disabled=0, is_group=0)):
            reject('Review the existing warehouse; it was not changed')
    else:
        warehouse = frappe.get_doc(dict(doctype='Warehouse', warehouse_name='LC Shop ' + shop.name,
            company=company.name, is_group=0)).insert(ignore_permissions=True).name
    shop.warehouse = warehouse
    shop.save(ignore_permissions=True)
    from local_commerce.services.owner import configure
    configure(shop.name, warehouse, shop.stock_adjustment_account, shop.cost_center)
    settings.setup_shop = shop.name
    settings.setup_complete = 1
    settings.setup_pending = 0
    settings.setup_message = ''
    settings.save(ignore_permissions=True)
    return status()


def install():
    """Fresh installs only. A failed bootstrap is rolled back without breaking install."""
    frappe.db.set_single_value('LC Store Settings', 'setup_pending', 1)
    resume()


def resume():
    if not frappe.db.get_single_value('LC Store Settings', 'setup_pending'):
        return
    frappe.db.savepoint('local_dot_bootstrap')
    try:
        initialize()
    except Exception:
        frappe.db.rollback(save_point='local_dot_bootstrap')
        frappe.log_error(title='Local dot installation setup', message=frappe.get_traceback())
        frappe.db.set_single_value('LC Store Settings', 'setup_message',
            'Basic setup needs review. Open Local dot Setup as an administrator and retry; details are in Error Log.')


def status():
    require_platform()
    settings = frappe.get_single('LC Store Settings')
    company = settings.get('gst_company')
    shop = frappe.get_doc('LC Shop', settings.setup_shop) if settings.get('setup_shop') else None
    company_ok = bool(company and frappe.db.exists('Company', dict(name=company, country='India', default_currency='INR')))
    shop_ok = bool(shop and shop.company == company and shop.business_model == 'Owned shop')
    accounting = bool(shop_ok and shop.selling_price_list and
        frappe.db.exists('Price List', dict(name=shop.selling_price_list, enabled=1, selling=1, currency='INR')))
    for doc, mapping in ((settings, PLATFORM_ACCOUNTS), (shop, SHOP_ACCOUNTS)):
        for field, spec in mapping.items():
            accounting = accounting and bool(doc and doc.get(field) and frappe.db.exists('Account',
                dict(name=doc.get(field), company=company, root_type=spec[1], disabled=0, is_group=0, account_currency='INR')))
    for doctype, value in [('Warehouse', shop.warehouse if shop else None),
            ('Cost Center', shop.cost_center if shop else None), ('Cost Center', settings.gst_cost_center)]:
        accounting = accounting and bool(value and frappe.db.exists(doctype,
            dict(name=value, company=company, disabled=0, is_group=0)))
    # Presence checks are deliberately separate from activation/CA approval.
    gst = all(settings.get(k) for k in ('gst_number','gst_legal_name','gst_state','gst_address','gst_sac'))
    bank = bool(company and frappe.db.exists('Bank Account', dict(company=company, is_company_account=1,
        disabled=0, bank_account_no=['!=', ''])))
    gateway = bool(frappe.db.exists('LC Payment Gateway', {'enabled': 1}))
    vendors = frappe.get_all('LC Shop', filters={'business_model':'Third-party vendor'},
        fields=['name','cashfree_enabled','cashfree_settlement_mode','cashfree_vendor_id','gst_enabled'])
    split = bool(vendors and all(v.cashfree_enabled and v.cashfree_settlement_mode == 'Easy Split'
        and v.cashfree_vendor_id for v in vendors))
    rules = bool(vendors and all(v.gst_enabled for v in vendors))
    checks = [
        ('Company created or linked', company_ok, company or 'Not linked', '/app/company'),
        ('Local dot marketplace created', bool(company_ok and settings.marketplace_name), settings.marketplace_name or 'Not configured', '/app/lc-store-settings'),
        ('Daily Basket shop created', shop_ok, shop.shop_name if shop else 'Not linked', '/admin/shops'),
        ('Warehouse and accounting checked', bool(accounting), 'Separate retail and marketplace ledgers; no bank details invented', '/admin/settings'),
        ('GST details configured', bool(gst), 'Identity fields entered; review tax accounts and treatment before live invoices', '/admin/gst'),
        ('Bank accounts configured', bank, 'Add real company bank details from shop settings', '/admin/shops'),
        ('Cashfree configured', gateway, 'Enabled profile present; verify credentials and test checkout', '/admin/cashfree'),
        ('Easy Split configured', split, 'Vendor IDs entered; confirm onboarding and settlement eligibility in Cashfree. Own shop uses Direct merchant', '/admin/cashfree'),
        ('Commission and vendor settlement rules configured', rules, 'Configure each third-party shop before enabling marketplace GST', '/admin/gst'),
    ]
    return dict(checks=[dict(label=a, complete=b, detail=c, link=d) for a,b,c,d in checks],
        message=settings.setup_message, initialized=bool(settings.setup_complete),
        company_confirmation=COMPANY if not company and frappe.db.exists('Company', COMPANY) else '',
        shop_choices=frappe.get_all('LC Shop', filters={'shop_name':SHOP}, fields=['name','shop_name','company','business_model']) if not shop else [])
