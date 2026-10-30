import frappe
from local_commerce.services import campaigns


@frappe.whitelist(methods=["GET"])
def preference():
    return campaigns.preference()


@frappe.whitelist(methods=["POST"])
def set_preference(enabled):
    return campaigns.preference(enabled)


@frappe.whitelist(methods=["GET"])
def options(shop=""):
    return campaigns.options(shop)


@frappe.whitelist(methods=["GET"])
def listing():
    return campaigns.listing()


@frappe.whitelist(methods=["POST"])
def save(shop, title, message, item=""):
    return campaigns.save(shop, title, message, item)


@frappe.whitelist(methods=["POST"])
def send(name, send_at=""):
    return campaigns.send(name, send_at)


@frappe.whitelist(methods=["POST"])
def test(name):
    return campaigns.test(name)


@frappe.whitelist(methods=["POST"])
def cancel(name):
    return campaigns.cancel(name)
