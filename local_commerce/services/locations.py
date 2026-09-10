"""Map configuration and shop location serialization."""

import frappe

from local_commerce.services.location_rules import point

DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_ATTRIBUTION = "© OpenStreetMap contributors"
DEFAULT_ATTRIBUTION_URL = "https://www.openstreetmap.org/copyright"


def map_config():
    tile_url = str(frappe.conf.get("lc_map_tile_url") or DEFAULT_TILE_URL).strip()
    if not tile_url.startswith("https://") or not all(
        token in tile_url for token in ("{z}", "{x}", "{y}")
    ):
        tile_url = DEFAULT_TILE_URL
    attribution = str(frappe.conf.get("lc_map_attribution") or DEFAULT_ATTRIBUTION).strip()
    attribution_url = str(
        frappe.conf.get("lc_map_attribution_url") or DEFAULT_ATTRIBUTION_URL
    ).strip()
    if not attribution_url.startswith("https://"):
        attribution_url = DEFAULT_ATTRIBUTION_URL
    return {
        "tile_url": tile_url,
        "attribution": attribution[:200],
        "attribution_url": attribution_url[:500],
    }


def shop_location(doc):
    try:
        location = point(doc.latitude, doc.longitude)
    except ValueError:
        location = None
    if not location:
        return None
    return {
        **location,
        "address_line1": doc.address_line1 or "",
        "city": doc.city or "",
        "postal_code": doc.postal_code or "",
        "service_radius_km": doc.service_radius_km or 0,
        "live_tracking_enabled": bool(doc.live_tracking_enabled),
    }
