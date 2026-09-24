import frappe

from local_commerce.services import push


@frappe.whitelist(methods=["GET"])
def status(endpoint=""):
    return push.status(endpoint)


@frappe.whitelist(methods=["POST"])
def subscribe(subscription):
    return push.subscribe(subscription)


@frappe.whitelist(methods=["POST"])
def unsubscribe(endpoint):
    return push.unsubscribe(endpoint)
