import frappe
from local_commerce.services import installation_setup


@frappe.whitelist(methods=['GET'])
def status():
    return installation_setup.status()


@frappe.whitelist(methods=['POST'])
def initialize(confirm_company='', confirm_shop=''):
    return installation_setup.initialize(confirm_company, confirm_shop)
