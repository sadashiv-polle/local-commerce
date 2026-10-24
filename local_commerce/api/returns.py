import frappe
from frappe.rate_limiter import rate_limit
from local_commerce.services import returns


@frappe.whitelist(methods=['POST'])
@rate_limit(limit=30, seconds=3600)
def request_return(order, reason):
    return returns.request_return(order, reason)


@frappe.whitelist(methods=['POST'])
def review(order, review_note):
    return returns.review(order, review_note)


@frappe.whitelist(methods=['POST'])
def decide(order, decision, decision_note, kind='Full', amount=None, credit_note=None):
    return returns.decide(order, decision, decision_note, kind, amount, credit_note)


@frappe.whitelist(methods=['POST'])
def retry(order):
    return returns.retry(order)


@frappe.whitelist(methods=['POST'])
def record_manual(order, credit_note, payment_entry, decision_note):
    return returns.record_manual(order, credit_note, payment_entry, decision_note)
