"""Owned shops share the platform Company; external shops use separate Companies."""
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
    if model != 'Legacy':
        platform = frappe.db.get_single_value('LC Store Settings', 'gst_company')
        if not platform:
            frappe.throw('Select the platform legal Company before creating shops')
        company = shop.get('company')
        if model == 'Owned shop' and company != platform:
            frappe.throw('Owned shops must use the platform legal Company')
        if model == 'Third-party vendor':
            if company == platform:
                frappe.throw('Third-party shops must use their own Company, not the platform Company')
            if frappe.db.exists('LC Shop', {'company': company, 'name': ['!=', shop.name]}):
                frappe.throw('This vendor Company is already linked to another shop')
    if model == 'Owned shop':
        if shop.get('gst_enabled'):
            frappe.throw('Owned shops use product tax templates, not marketplace commission GST')
        if float(shop.get('cashfree_commission') or 0):
            frappe.throw('Do not charge marketplace commission to your own shop')
        if shop.get('cashfree_settlement_mode') == 'Easy Split':
            frappe.throw('Use Direct merchant settlement for your own shop')


def select_platform(company):
    require_platform()
    frappe.db.sql('select name from `tabDocType` where name=%s for update', ('LC Store Settings',))
    current = frappe.db.get_single_value('LC Store Settings', 'gst_company')
    company = company or current
    if not company or not frappe.db.exists('Company', company):
        frappe.throw('Select the existing platform legal Company (for example Shiv Tech Works)')
    if current and current != company:
        frappe.throw('Platform Company is already configured; review GST settings before changing it')
    if not current:
        settings = frappe.get_single('LC Store Settings')
        settings.gst_company = company
        settings.save(ignore_permissions=True)
    return company


def validate_platform_change(settings):
    previous = settings.get_doc_before_save()
    if previous and previous.get('gst_company') != settings.get('gst_company'):
        if frappe.db.exists('LC Shop', {'business_model': ['in', ['Owned shop','Third-party vendor']]}):
            frappe.throw('Platform Company cannot change after classified shops exist; an accounting migration is required')


def create_vendor_company(shop):
    require_platform()
    if shop.get('business_model') != 'Third-party vendor':
        frappe.throw('Select the existing platform Company for your own shop')
    name = str(shop.get('gst_legal_name') or '').strip()
    if not name or len(name) > 140:
        frappe.throw('Enter the vendor legal business name for the new Company')
    if frappe.db.exists('Company', name):
        frappe.throw('This Company already exists. Select it explicitly instead of creating a duplicate')
    if not shop.company_country or not shop.company_currency:
        frappe.throw('Select the vendor Company country and currency')
    abbr = 'LC' + frappe.generate_hash(length=8).upper()
    while frappe.db.exists('Company', {'abbr': abbr}):
        abbr = 'LC' + frappe.generate_hash(length=8).upper()
    company = frappe.get_doc(dict(doctype='Company', company_name=name, abbr=abbr,
        country=shop.company_country, default_currency=shop.company_currency,
        create_chart_of_accounts_based_on='Standard Template', chart_of_accounts='Standard'))
    if shop.get('gst_registration') == 'Registered' and frappe.get_meta('Company').has_field('gstin'):
        company.gstin = shop.get('gst_number')
    company.insert(ignore_permissions=True)
    shop.company = company.name
