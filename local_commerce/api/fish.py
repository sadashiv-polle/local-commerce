import frappe

from local_commerce.services import fish


@frappe.whitelist(methods=['GET'])
def snapshot(shop):
    return fish.snapshot(shop)


@frappe.whitelist(methods=['POST'])
def adjust(shop, item, action, quantity, reason, request_key, unit_cost=0,
           validity_hours=None, lot=None):
    return fish.adjust(shop, item, action, quantity, reason, request_key, unit_cost,
                       validity_hours, lot)


@frappe.whitelist(methods=['POST'])
def adopt(shop, item, validity_hours, request_key):
    return fish.adopt(shop, item, validity_hours, request_key)


@frappe.whitelist(methods=['GET'])
def report(shop, start_date, end_date):
    from local_commerce.services.fish_reports import report as build_report

    return build_report(shop, start_date, end_date)


@frappe.whitelist(methods=['GET'])
def expense_accounts(shop):
    from local_commerce.permissions.scope import require_platform

    require_platform()
    company = frappe.db.get_value('LC Shop', shop, 'company')
    return frappe.get_all('Account', filters={'company': company, 'root_type': 'Expense',
                                              'is_group': 0, 'disabled': 0},
                          pluck='name', limit_page_length=500)
