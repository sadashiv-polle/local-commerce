import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import scheduled


@frappe.whitelist(allow_guest=True, methods=['GET'])
def slots(shop):
    return scheduled.slots(shop)


@frappe.whitelist(methods=['GET'])
def settings(shop):
    return scheduled.settings(shop)


@frappe.whitelist(methods=['POST'])
def configure(shop, normal, scheduled_enabled):
    return scheduled.configure(shop, normal, scheduled_enabled)


@frappe.whitelist(methods=['POST'])
def save_slot(shop, values, name=None):
    return scheduled.save_slot(shop, values, name)


@frappe.whitelist(methods=['POST'])
def assign(slot, delivery_user):
    return scheduled.assign(slot, delivery_user)


@frappe.whitelist(methods=['GET'])
@rate_limit(limit=60, seconds=3600)
def route(slot):
    return scheduled.route(slot)


@frappe.whitelist(methods=['GET'])
def rider_batches():
    return scheduled.rider_batches()
