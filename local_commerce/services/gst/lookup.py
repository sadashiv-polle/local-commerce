"""Optional India Compliance adapter. Lookup never changes business records."""
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject
from local_commerce.services.gst.rules import gstin


def normalize(number, data):
    if not isinstance(data, dict) or str(data.get('gstin') or '').upper() != number:
        reject('GST lookup returned no matching registration. Check the GSTIN or enter details manually.')
    def text(value, size=140):
        return str(value or '').strip()[:size]
    address = (data.get('pradr') or {}).get('addr') or {}
    parts = []
    for key in ('bno', 'flno', 'bnm', 'st', 'loc', 'city', 'dst', 'stcd', 'pncd'):
        part = text(address.get(key))
        if part and part not in parts:
            parts.append(part)
    return dict(gstin=number, legal_name=text(data.get('lgnm')),
        trade_name=text(data.get('tradeNam')), status=text(data.get('sts')),
        address=', '.join(parts)[:1000], city=text(address.get('city') or address.get('dst')),
        postal_code=text(address.get('pncd'), 20), state=number[:2],
        category=text(data.get('dty')))


def lookup(number):
    require_platform()
    try:
        number = gstin(str(number or '').strip().upper())
    except ValueError as exc:
        reject(str(exc))
    if 'india_compliance' not in frappe.get_installed_apps():
        reject('GST lookup needs India Compliance installed and its GST API configured. You can enter details manually.')
    settings = frappe.get_single('GST Settings')
    if settings.get('sandbox_mode'):
        reject('GSTIN lookup is unavailable in India Compliance sandbox. Use manual details for demo testing.')
    if settings.get('enable_api') is not None and not settings.get('enable_api'):
        reject('Enable API features in ERPNext GST Settings and configure your India Compliance account first.')
    # Credentials and transport remain entirely in India Compliance on the server.
    try:
        from india_compliance.gst_india.api_classes.public import PublicAPI
        response = PublicAPI().get_gstin_info(number)
    except Exception:
        frappe.log_error(title='Local dot GSTIN lookup', message=frappe.get_traceback())
        reject('GST lookup could not complete. Check India Compliance API access, credits and sandbox settings, or enter details manually.')
    return normalize(number, response)
