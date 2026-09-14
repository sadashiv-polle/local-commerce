"""Small, cached place-search proxy for editable maps."""

import hashlib
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import frappe
from redis.exceptions import LockError

from local_commerce.services.location_rules import point

DEFAULT_ENDPOINT = "https://nominatim.openstreetmap.org/search"
COUNTRY_CODES = re.compile(r"^[a-z]{2}(,[a-z]{2})*$")


def reject(message):
    frappe.local.response["lc_message"] = message
    frappe.throw(message)


def _clean(value, limit):
    return str(value or "").strip()[:limit]


def _result(row):
    address = row.get("address") if isinstance(row.get("address"), dict) else {}
    street = _clean(address.get("road") or address.get("pedestrian") or address.get("path"), 120)
    number = _clean(address.get("house_number"), 20)
    line1 = " ".join(part for part in (number, street) if part)
    if not line1:
        line1 = _clean(address.get("amenity") or address.get("shop") or address.get("building"), 140)
    city = _clean(
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county"),
        100,
    )
    location = point(row.get("lat"), row.get("lon"), required=True)
    return {
        "label": _clean(row.get("display_name"), 300),
        **location,
        "address_line1": line1,
        "city": city,
        "postal_code": _clean(address.get("postcode"), 20).upper(),
    }


def search(query):
    if frappe.session.user == "Guest":
        frappe.throw("Sign in to search for a delivery location", frappe.PermissionError)
    query = " ".join(str(query or "").split())
    if not 3 <= len(query) <= 120:
        reject("Enter at least 3 characters to search for a place")

    endpoint = str(frappe.conf.get("lc_geocoder_url") or DEFAULT_ENDPOINT).strip()
    if not endpoint.startswith("https://"):
        reject("Place search is not configured securely")
    countries = str(frappe.conf.get("lc_geocoder_countrycodes") or "in").lower().strip()
    if not COUNTRY_CODES.fullmatch(countries):
        countries = "in"
    cache_key = "lc-place-search:" + hashlib.sha256(
        f"{endpoint}|{countries}|{query.casefold()}".encode()
    ).hexdigest()
    cached = frappe.cache.get_value(cache_key)
    if cached is not None:
        return cached

    try:
        with frappe.cache.lock("lc-place-search-request", timeout=15, blocking_timeout=4):
            cached = frappe.cache.get_value(cache_key)
            if cached is not None:
                return cached
            last_request = float(frappe.cache.get_value("lc-place-search-last-request") or 0)
            delay = 1.05 - (time.time() - last_request)
            if delay > 0:
                time.sleep(delay)
            url = endpoint + "?" + urlencode(
                {
                    "q": query,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "limit": 5,
                    "countrycodes": countries,
                }
            )
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "Accept-Language": str(getattr(frappe.local, "lang", None) or "en")[:12],
                    "Referer": "https://webcheckly.shop/",
                    "User-Agent": "LocalCommerce/0.1 (+https://webcheckly.shop)",
                },
            )
            try:
                with urlopen(request, timeout=8) as response:  # nosec B310 - HTTPS checked above
                    content = response.read(131073)
            finally:
                frappe.cache.set_value(
                    "lc-place-search-last-request", time.time(), expires_in_sec=60
                )
            if len(content) > 131072:
                raise ValueError("Place-search response is too large")
            rows = json.loads(content)
            if not isinstance(rows, list):
                raise ValueError("Unexpected place-search response")
            results = [_result(row) for row in rows[:5] if isinstance(row, dict)]
            frappe.cache.set_value(cache_key, results, expires_in_sec=86400)
            return results
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
        reject("Place search is temporarily unavailable. Tap the map or try again shortly")
    except LockError:
        reject("Place search is busy. Please wait a moment and try again")
