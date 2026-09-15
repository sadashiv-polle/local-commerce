import frappe

from local_commerce.services import notifications


@frappe.whitelist(methods=["GET"])
def list_notifications(start=0):
    return notifications.list_notifications(start)


@frappe.whitelist(methods=["POST"])
def mark_read(name):
    return notifications.mark_read(name)


@frappe.whitelist(methods=["POST"])
def mark_all_read():
    return notifications.mark_all_read()
