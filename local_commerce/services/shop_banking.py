"""Native ERPNext Bank/Bank Account onboarding, without changing Company defaults."""
import hashlib
import re
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject


def parse_details(values):
    values = frappe.parse_json(values) if values else {}
    if not isinstance(values, dict) or set(values) - {'mode','existing','bank','holder','number','confirm_number','ifsc'}:
        reject('Invalid bank setup details')
    mode = values.get('mode', 'later')
    if mode not in ('later','existing','new'):
        reject('Choose an existing bank account, a new account, or add later')
    if mode == 'later':
        return {'mode': mode}
    if mode == 'existing':
        name = str(values.get('existing') or '').strip()
        if not name or len(name) > 140:
            reject('Select a Company Bank Account')
        return dict(mode=mode, existing=name)
    result = {key:str(values.get(key) or '').strip() for key in ('bank','holder','number','confirm_number','ifsc')}
    if any(not result[key] or len(result[key]) > 80 or any(ord(c)<32 for c in result[key]) for key in ('bank','holder')):
        reject('Enter the bank name and account holder name, up to 80 characters')
    # Keep leading zeroes. Do not cast bank account numbers to integers.
    if not re.fullmatch(r'[0-9]{6,34}',result['number']):
        reject('Enter a bank account number containing 6–34 digits')
    if result['number'] != result['confirm_number']:
        reject('Bank account numbers do not match')
    result['ifsc'] = result['ifsc'].upper()
    if not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', result['ifsc']):
        reject('Enter an 11-character IFSC, with zero as its fifth character')
    result.pop('confirm_number')
    return dict(mode=mode, **result)


def ifsc_field():
    # Standard ERPNext uses branch_code; respect an installed IFSC field when present.
    meta = frappe.get_meta('Bank Account')
    return next((f for f in ('ifsc_code','ifsc') if meta.has_field(f)), 'branch_code')


def checked_account(name, company):
    bank = frappe.get_doc('Bank Account', name)
    if bank.disabled or not bank.is_company_account or bank.company != company or not bank.account or bank.get('is_credit_card'):
        reject('Select an enabled Company Bank Account belonging to this shop Company')
    ledger = frappe.get_doc('Account', bank.account)
    if (ledger.company != company or ledger.disabled or ledger.is_group or ledger.root_type != 'Asset'
            or ledger.account_type != 'Bank' or ledger.account_currency != 'INR'):
        reject('The bank account must link to an active INR Bank ledger in this Company')
    code = str(bank.get(ifsc_field()) or bank.get('branch_code') or '').strip().upper()
    if not bank.bank_account_no or not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}',code):
        reject('Complete the bank account number and valid IFSC on the ERPNext Bank Account first')
    return bank


def configure(shop, values):
    require_platform()
    details = parse_details(values)
    if details['mode'] == 'later':
        return None
    company = frappe.get_doc('Company', shop.company, for_update=True)
    if company.country != 'India' or company.default_currency != 'INR':
        reject('This bank onboarding supports Indian INR Company accounts')
    if details['mode'] == 'existing':
        bank = checked_account(details['existing'],shop.company)
    else:
        found = frappe.db.get_value('Bank Account', dict(company=shop.company,
            is_company_account=1,bank=details['bank'],bank_account_no=details['number']), 'name')
        if found:
            bank = checked_account(found,shop.company)
            code = str(bank.get(ifsc_field()) or bank.get('branch_code') or '').strip().upper()
            if code != details['ifsc']:
                reject('An account with this number already exists with a different IFSC; review it in ERPNext')
        else:
            if not frappe.db.exists('Bank',details['bank']):
                frappe.get_doc(dict(doctype='Bank',bank_name=details['bank'])).insert(ignore_permissions=True)
            from local_commerce.services.shop_onboarding import ensure_account
            token = hashlib.sha256((shop.company+'|'+details['bank']+'|'+details['number']).encode()).hexdigest()[:12]
            ledger = ensure_account(shop.company,'LC Bank '+token,'Asset','Bank')
            if frappe.db.exists('Bank Account',{'account':ledger}):
                reject('The selected bank ledger already has a Bank Account; review it in ERPNext')
            bank = frappe.get_doc(dict(doctype='Bank Account',
                account_name=details['holder'][:min(70,124-len(details['bank']))]+' '+token,
                bank=details['bank'],bank_account_no=details['number'],branch_code=details['ifsc'],
                is_company_account=1,company=shop.company,account=ledger,is_default=0,disabled=0))
            bank.set(ifsc_field(),details['ifsc'])
            # Insert normally: ERPNext and installed India Compliance hooks remain active.
            bank.insert(ignore_permissions=True)
            bank = checked_account(bank.name,shop.company)
    shop.cashfree_bank_account = bank.account
    shop.upi_bank_account = bank.account
    return bank.name


def options():
    require_platform()
    filters = {'is_company_account': 1, 'disabled': 0}
    # Older ERPNext v15 schemas do not have the optional credit-card column.
    if frappe.db.has_column('Bank Account', 'is_credit_card'):
        filters['is_credit_card'] = 0
    rows = frappe.get_all('Bank Account',filters=filters,
        fields=['name','bank','company','account','bank_account_no'],limit_page_length=0)
    # Full account numbers never enter the options response or public shop responses.
    return [dict(name=r.name,bank=r.bank,company=r.company,account=r.account,
                 last_four=str(r.bank_account_no or '')[-4:]) for r in rows]


def shop_settings(shop):
    require_platform()
    doc = frappe.get_doc('LC Shop', shop)
    return dict(company=doc.company, upi_ledger=doc.get('upi_bank_account'),
        settlement_ledger=doc.get('cashfree_bank_account'),
        accounts=[row for row in options() if row['company'] == doc.company],
        banks=frappe.get_all('Bank',pluck='name',order_by='name',limit_page_length=0))


def save_shop_bank(shop, details, usage='store'):
    require_platform()
    if usage not in ('store','upi','settlement','both'):
        reject('Choose how this shop will use the bank account')
    parsed = parse_details(details)
    if parsed['mode'] == 'later':
        reject('Enter bank details or select an existing account')
    company = frappe.db.get_value('LC Shop', shop, 'company')
    frappe.get_doc('Company', company, for_update=True)
    doc = frappe.get_doc('LC Shop', shop, for_update=True)
    if doc.company != company:
        reject('The shop Company changed; reload and try again')
    old_upi, old_settlement = doc.get('upi_bank_account'), doc.get('cashfree_bank_account')
    # Pass original input so confirmation validation is retained for new accounts.
    name = configure(doc, details)
    if usage not in ('upi','both'):
        doc.upi_bank_account = old_upi
    if usage not in ('settlement','both'):
        doc.cashfree_bank_account = old_settlement
    if usage != 'store':
        doc.save()
    return dict(bank_account=name, usage=usage)
