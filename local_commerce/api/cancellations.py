"""Customer, owner and admin cancellation endpoints. No client financial amounts."""
import json
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services import marketplace as service


@frappe.whitelist(methods=['POST'])
def request(order, reason):
    return service.initiate(order, reason)


@frappe.whitelist(methods=['POST'])
def decide(order, decision, note, role):
    return service.approve(order, decision, note, role)


@frappe.whitelist(methods=['POST'])
def retry(order):
    return service.retry(order)


@frappe.whitelist(methods=['GET'])
def activity(order):
    doc = frappe.get_doc('LC Order', order)
    role = service.access(doc)
    events = frappe.get_all('LC Marketplace Event', filters={'order':order},
        fields=['event_type','creation','data_json'], order_by='creation asc', limit_page_length=0)
    operations = []
    if role == 'Admin':
        operations = frappe.get_all('LC Marketplace Operation', filters={'order':order},
            fields=['name','kind','status','payload_json','response_json'], order_by='creation asc', limit_page_length=0)
    # Provider references, actor details and internal ledger are restricted to staff.
    return dict(case=service.public(doc), events=events if role in ('Admin','Shop') else [], operations=operations)


@frappe.whitelist(methods=['GET'])
def queue(start=0):
    require_platform()
    start = max(0, int(start))
    rows = frappe.get_all('LC Order', filters={'cancellation_policy_json':['is','set']},
        fields=['name','shop','status','cancellation_state','marketplace_settlement_state','cancellation_json'],
        order_by='modified desc', start=start, limit_page_length=30)
    for row in rows:
        row['cancellation'] = json.loads(row.pop('cancellation_json') or '{}')
    return rows


@frappe.whitelist(methods=['POST'])
def settlement_check(order):
    return service.settlement_check(order)


@frappe.whitelist(methods=['POST'])
def retry_operation(order, operation_name):
    return service.retry_operation(order, operation_name)
