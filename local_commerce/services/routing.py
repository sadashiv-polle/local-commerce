"""Cached road routes for delivery maps."""

import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import frappe
from redis.exceptions import LockError

from local_commerce.services.location_rules import point

DEFAULT_ENDPOINT = "https://router.project-osrm.org/route/v1/driving"


def reject(message):
    frappe.local.response["lc_message"] = message
    frappe.throw(message)


def _endpoint():
    endpoint = str(frappe.conf.get("lc_routing_url") or DEFAULT_ENDPOINT).strip().rstrip("/")
    if not endpoint.startswith("https://"):
        reject("Delivery routing is not configured securely")
    return endpoint


def _coordinates(value):
    if not isinstance(value, list) or not 2 <= len(value) <= 5000:
        raise ValueError("Unexpected delivery route")
    result = []
    for row in value:
        if not isinstance(row, list) or len(row) < 2:
            raise ValueError("Unexpected delivery route")
        location = point(row[1], row[0], required=True)
        result.append(location)
    return result


def road_route(origin, destination):
    start = point(origin.get("latitude"), origin.get("longitude"), required=True)
    finish = point(destination.get("latitude"), destination.get("longitude"), required=True)
    endpoint = _endpoint()
    signature = "|".join(
        [
            endpoint,
            f"{start['latitude']:.5f},{start['longitude']:.5f}",
            f"{finish['latitude']:.5f},{finish['longitude']:.5f}",
        ]
    )
    cache_key = "lc-delivery-route:" + hashlib.sha256(signature.encode()).hexdigest()
    cached = frappe.cache.get_value(cache_key)
    if cached is not None:
        return cached

    try:
        with frappe.cache.lock(cache_key + ":request", timeout=20, blocking_timeout=5):
            cached = frappe.cache.get_value(cache_key)
            if cached is not None:
                return cached
            coordinates = (
                f"{start['longitude']},{start['latitude']};"
                f"{finish['longitude']},{finish['latitude']}"
            )
            url = f"{endpoint}/{coordinates}?" + urlencode(
                {"overview": "simplified", "geometries": "geojson", "steps": "false"}
            )
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "Referer": "https://webcheckly.shop/",
                    "User-Agent": "LocalCommerce/0.1 (+https://webcheckly.shop)",
                },
            )
            with urlopen(request, timeout=10) as response:  # nosec B310 - HTTPS checked above
                content = response.read(524289)
            if len(content) > 524288:
                raise ValueError("Delivery route response is too large")
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("Unexpected delivery route")
            routes = payload.get("routes")
            if payload.get("code") != "Ok" or not isinstance(routes, list) or not routes:
                raise ValueError("No delivery route found")
            selected = routes[0]
            geometry = selected.get("geometry") if isinstance(selected, dict) else None
            result = {
                "points": _coordinates(geometry.get("coordinates") if geometry else None),
                "distance_km": round(float(selected.get("distance") or 0) / 1000, 1),
                "duration_minutes": max(1, round(float(selected.get("duration") or 0) / 60)),
                "attribution": "Route by OSRM · © OpenStreetMap contributors",
                "attribution_url": "https://project-osrm.org/",
            }
            frappe.cache.set_value(cache_key, result, expires_in_sec=86400)
            return result
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, TypeError, ValueError):
        reject("Road route is temporarily unavailable. You can still open navigation")
    except LockError:
        reject("Road route is busy. Please wait a moment and try again")
