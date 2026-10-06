import frappe

from local_commerce.services.session import get_context


@frappe.whitelist(allow_guest=True, methods=["GET"])
def context():
    return get_context()


@frappe.whitelist(methods=["POST"])
def logout():
    frappe.local.login_manager.logout()
    return {"logged_out": True}


from frappe.rate_limiter import rate_limit


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=300)
def change_password(current_password, new_password):
    from frappe.core.doctype.user.user import update_password
    from local_commerce.services.owner import reject
    if frappe.session.user == 'Guest':
        frappe.throw('Login required', frappe.PermissionError)
    if not isinstance(current_password, str) or not 1 <= len(current_password) <= 1000:
        reject('Enter your current password')
    if not isinstance(new_password, str) or not 8 <= len(new_password) <= 1000:
        reject('Use a new password between 8 and 1000 characters')
    if current_password == new_password:
        reject('Choose a different new password')
    try:
        update_password(new_password=new_password, old_password=current_password, logout_all_sessions=1)
    except frappe.AuthenticationError:
        reject('Current password is incorrect. Try again or request a reset email.')
    return {'updated': True}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=3, seconds=3600)
def password_reset_email():
    from local_commerce.services.password_reset import request
    from local_commerce.services.owner import reject
    if frappe.session.user in {'Guest', 'Administrator'}:
        reject('Use your current password to change this account password')
    email = frappe.db.get_value('User', frappe.session.user, 'email')
    return request(email)
