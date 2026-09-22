import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import scheduled


@frappe.whitelist(allow_guest=True, methods=['GET'])
def slots(shop):
    return scheduled.slots(shop)


@frappe.whitelist(methods=['GET'])
def settings(shop, start=0):
    return scheduled.settings(shop, start)


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


@frappe.whitelist(methods=['GET'])
def batch_actions(slot):
    return scheduled.batch_actions(slot)


@frappe.whitelist(methods=['POST'])
def advance_batch(slot, target):
    return scheduled.advance_batch(slot, target)


@frappe.whitelist(methods=['GET'])
def tracking_anchor(slot):
    return scheduled.tracking_anchor(slot)


@frappe.whitelist(methods=['POST'])
def save_schedule(shop, values, name=None):
    from local_commerce.services.recurring_delivery import save_schedule as save

    return save(shop, values, name)


@frappe.whitelist(methods=['POST'])
def delete_schedule(name):
    from local_commerce.services.recurring_delivery import remove_schedule

    return remove_schedule(name)


@frappe.whitelist(methods=['POST'])
def delete_slot(name):
    return scheduled.delete_slot(name)
