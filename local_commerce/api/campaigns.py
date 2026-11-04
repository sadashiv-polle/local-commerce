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
def save(shop, title, message, item="", template_id="", template_script="latin", campaign_audience="All", campaign_period=""):
    return campaigns.save(shop, title, message, item, template_id, template_script, campaign_audience, campaign_period)


@frappe.whitelist(methods=["POST"])
def send(name, send_at=""):
    return campaigns.send(name, send_at)


@frappe.whitelist(methods=["POST"])
def test(name):
    return campaigns.test(name)


@frappe.whitelist(methods=["POST"])
def cancel(name):
    return campaigns.cancel(name)


@frappe.whitelist(methods=["GET"])
def wording_history(shop, item=""):
    return campaigns.wording_history(shop, item)


@frappe.whitelist(methods=["POST"])
def template_settings(value):
    from local_commerce.services.campaign_templates import configure
    return configure(value)
