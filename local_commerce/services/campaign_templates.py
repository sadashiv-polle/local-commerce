"""Goan campaign wording and eligibility; uses the existing campaign pipeline."""
import json
from functools import lru_cache
from pathlib import Path

import frappe
from frappe.utils import now_datetime
from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject

FISH = {'fish', 'bangde', 'talle', 'isvon', 'chonak'}
PERIODS = {'': (0, 24), 'morning': (8, 10), 'lunch': (12, 14), 'evening': (17, 19)}
AUDIENCES = {'All', 'Shop customers'}


@lru_cache(maxsize=1)
def library():
    return json.loads((Path(__file__).resolve().parents[1] / 'campaign_goan_copy.json').read_text())


def settings():
    raw = frappe.db.get_single_value('LC Store Settings', 'campaign_goan_settings')
    return validate_settings(json.loads(raw) if raw else {})


def validate_settings(value):
    if not isinstance(value, dict):
        reject('Invalid template settings')
    disabled = value.get('disabled', [])
    tags = value.get('fish_tags', {})
    ids = {row['id'] for row in library()}
    if not isinstance(disabled, list) or any(not isinstance(x, str) or x not in ids for x in disabled):
        reject('Invalid template selection')
    if not isinstance(tags, dict) or any(not isinstance(k, str) or (not isinstance(v, str) or v not in FISH) for k, v in tags.items()):
        reject('Choose a supported fish type')
    script = value.get('script', 'latin')
    start, end = value.get('start', 8), value.get('end', 19)
    if script not in ('latin', 'devanagari') or type(start) is not int or type(end) is not int or not 0 <= start < end <= 24:
        reject('Choose valid script and daytime hours')
    automatic = value.get('automatic', False)
    if type(automatic) is not bool:
        reject('Invalid automatic setting')
    return dict(disabled=list(dict.fromkeys(disabled)), fish_tags=tags, script=script,
                start=start, end=end, automatic=automatic)


def configure(value):
    require_platform()
    config = validate_settings(json.loads(value) if isinstance(value, str) else value)
    for item in config['fish_tags']:
        if not frappe.db.exists('Item', item):
            reject('Unknown product in fish settings')
    frappe.db.set_single_value('LC Store Settings', 'campaign_goan_settings', json.dumps(config))
    return config


def template(template_id):
    return next((row for row in library() if row['id'] == template_id), None)


def matches(row, item, config):
    tag = config['fish_tags'].get(item)
    return bool(tag and (row['fish'] == 'fish' or row['fish'] == tag))


def time_allowed(row, now, config, period=''):
    if row['weekdays'] and now.weekday() not in row['weekdays']:
        return False
    hour = now.hour + now.minute / 60
    windows = [(config['start'], config['end']), PERIODS[row['period']], PERIODS[period]]
    return all(start <= hour < end for start, end in windows)


def validate_campaign(template_id, script, item, audience, period):
    if audience not in AUDIENCES or period not in PERIODS:
        reject('Choose a valid audience and time window')
    if not template_id:
        return
    config, row = settings(), template(template_id)
    if script not in ('latin', 'devanagari') or not row or template_id in config['disabled']:
        reject('Choose an enabled Goan template and script')
    if not matches(row, item, config):
        reject('Choose a matching product and set its fish type first')


def delivery_state(doc, now=None):
    """ready, wait, or a permanent suppression reason for this notification."""
    now = now or now_datetime()
    if doc.item:
        from local_commerce.services.orders import public_product
        from local_commerce.services.stock_alerts import restocked
        try:
            if not restocked(public_product(doc.shop, doc.item)):
                return 'Product unavailable'
        except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError):
            return 'Product unavailable'
    period = doc.get('campaign_period') or ''
    if period not in PERIODS:
        return 'Invalid time window'
    template_id = doc.get('template_id')
    if template_id:
        config, row = settings(), template(template_id)
        if not row or template_id in config['disabled']:
            return 'Template disabled'
        if not matches(row, doc.item, config):
            return 'Product no longer matches template'
        if not time_allowed(row, now, config, period):
            return 'wait'
    elif not PERIODS[period][0] <= now.hour < PERIODS[period][1]:
        return 'wait'
    return 'ready'


def automatic_choice(shop, item, now):
    config = settings()
    if not config['automatic']:
        return None
    candidates = [row for row in library() if row['id'] not in config['disabled']
                  and matches(row, item, config) and time_allowed(row, now, config)]
    if not candidates:
        return None
    history = frappe.get_all('LC Campaign', filters={'shop': shop, 'item': item},
                             fields=['template_id'], order_by='creation desc', limit_page_length=0)
    used = [row.get('template_id') for row in history]
    candidates.sort(key=lambda row: used.index(row['id']) if row['id'] in used else float('inf'), reverse=True)
    row = candidates[0]
    return dict(template_id=row['id'], template_script=config['script'], **row[config['script']])
