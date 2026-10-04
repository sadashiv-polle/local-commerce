"""Short automatic usernames for verified Localdot signups."""
import secrets
import unicodedata

import frappe

from local_commerce.services.owner import reject


def first_name_base(full_name):
    first = str(full_name or '').strip().split()
    first = unicodedata.normalize('NFKC', first[0] if first else '').lower()
    return ''.join(character for character in first if character.isalnum())[:40] or 'user'


def allocate(full_name):
    # Hold until transaction completion, not just until the candidate is chosen.
    # This serializes Localdot signups across web workers.
    frappe.db.sql('select name from `tabUser` where name=%s for update', ('Administrator',))
    base = first_name_base(full_name)
    for attempt in range(101):
        digits = 3 if attempt <= 50 else 4
        candidate = base if attempt == 0 else base + str(
            secrets.randbelow(9 * 10 ** (digits - 1)) + 10 ** (digits - 1))
        # A locking read sees committed users even if this request's earlier
        # verification reads established an older repeatable-read snapshot.
        exists = frappe.db.sql(
            'select name from `tabUser` where lower(username)=%s or lower(name)=%s for update',
            (candidate, candidate),
        )
        if not exists:
            return candidate
    reject('Could not assign a username. Please retry signup.')
