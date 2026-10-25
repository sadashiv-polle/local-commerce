"""Use Frappe's Google OAuth flow; never exchange credentials in the browser."""
import re
import frappe


def safe_destination(next_page=None):
    if (not isinstance(next_page, str) or len(next_page) > 1000
            or re.search(r'[\\\x00-\x1f\x7f#]', next_page)
            or not re.match(r'^/(store|shop|orders|account|delivery|favourites|categories)(/|\?|$)', next_page)):
        next_page = '/store'
    return '/local-commerce#' + next_page


def google_enabled():
    return bool(frappe.db.exists('Social Login Key', {
        'name': 'google', 'social_login_provider': 'Google',
        'enable_social_login': 1, 'client_id': ['!=', ''],
    }))


def google_authorize(next_page=None):
    if not google_enabled():
        frappe.throw('Google sign-in is not configured. Please use email login for now.')
    # Frappe applies the Portal default role when creating/linking OAuth users.
    # Reject elevated defaults instead of silently changing administrator settings.
    role = frappe.db.get_single_value('Portal Settings', 'default_role')
    if role not in (None, '', 'Customer', 'LC Customer'):
        frappe.throw('Ask the administrator to set a customer-only default role in Portal Settings before enabling Google sign-in.')
    from frappe.utils.oauth import get_oauth2_authorize_url
    return {'url': get_oauth2_authorize_url('google', safe_destination(next_page))}
