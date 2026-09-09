import frappe

from local_commerce.services.session import get_context


@frappe.whitelist(allow_guest=True, methods=["GET"])
def context():
    return get_context()


@frappe.whitelist(methods=["POST"])
def logout():
    frappe.local.login_manager.logout()
    return {"logged_out": True}
