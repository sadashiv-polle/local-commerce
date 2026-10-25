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


def on_login(login_manager):
    """Welcome only successful Google sessions, never failed OAuth attempts."""
    request = getattr(frappe.local, 'request', None)
    if not request or request.path != '/api/method/frappe.integrations.oauth2_logins.login_via_google':
        return
    user = login_manager.user
    if not user or user in ('Guest', 'Administrator'):
        return
    frappe.enqueue('local_commerce.services.social_login.queue_welcome',
        user=user, queue='short', enqueue_after_commit=True)


def queue_welcome(user):
    """Queue once per customer, atomically with a durable marker; SMTP retries use Email Queue."""
    from frappe.utils import escape_html, get_url, now_datetime
    if not user or user in ('Guest', 'Administrator'):
        return
    frappe.db.sql('select name from `tabUser` where name=%s for update', (user,))
    account = frappe.get_doc('User', user)
    if (not account.enabled or account.user_type != 'Website User'
            or account.get('lc_google_welcome_queued_at')
            or not account.get_social_login_userid('google')):
        return
    name = escape_html(account.first_name or 'there')
    url = escape_html(get_url('/local-commerce#/store'))
    frappe.sendmail(
        recipients=[account.email],
        subject='Welcome to Local dot!',
        message=f'<p>Hi {name},</p><p>Welcome to Local dot — your neighbourhood shops, together.</p>'
        '<p>Your Google sign-in is ready. Add your delivery address, explore nearby shops, '
        'and place your first order.</p>'
        f'<p><a href="{url}">Start shopping on Local dot</a></p>'
        '<p>You can use Continue with Google whenever you return. '
        'You do not need to create a separate password to shop.</p>'
        '<p>Thank you,<br>The Local dot team</p>',
        reference_doctype='User', reference_name=user,
        now=False,
    )
    # No User.save(): it can re-trigger password notifications or other User hooks.
    frappe.db.set_value('User', user, 'lc_google_welcome_queued_at', now_datetime(), update_modified=False)
