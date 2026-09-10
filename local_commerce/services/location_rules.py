"""Pure coordinate validation and distance calculations."""

import math
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def coordinate(value, label, minimum, maximum):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Enter a valid {label}") from None
    if not result.is_finite() or result < Decimal(str(minimum)) or result > Decimal(str(maximum)):
        raise ValueError(f"Enter a valid {label}")
    return float(result.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def point(latitude, longitude, required=False):
    latitude_empty = latitude is None or str(latitude).strip() == ""
    longitude_empty = longitude is None or str(longitude).strip() == ""
    if latitude_empty and longitude_empty and not required:
        return None
    if latitude_empty or longitude_empty:
        raise ValueError("Select a complete location on the map")
    return {
        "latitude": coordinate(latitude, "latitude", -90, 90),
        "longitude": coordinate(longitude, "longitude", -180, 180),
    }


def distance_km(origin, destination):
    lat1, lon1 = math.radians(origin["latitude"]), math.radians(origin["longitude"])
    lat2, lon2 = math.radians(destination["latitude"]), math.radians(destination["longitude"])
    latitude_delta = lat2 - lat1
    longitude_delta = lon2 - lon1
    value = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(longitude_delta / 2) ** 2
    )
    value = min(1, max(0, value))
    return round(6371.0088 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value)), 3)


def delivery_match(origin, destination, radius, postcodes, postal_code, accepting=True):
    distance = distance_km(origin, destination) if origin else None
    normalized = {str(value).strip().upper() for value in postcodes if str(value).strip()}
    postal_code = str(postal_code or "").strip().upper()
    serviceable = bool(
        accepting and origin and radius > 0 and postal_code in normalized and distance <= radius
    )
    if serviceable:
        reason = "Delivers to this address"
    elif not accepting:
        reason = "Delivery setup pending"
    elif not origin:
        reason = "Shop map location unavailable"
    elif postal_code not in normalized:
        reason = "Postal code not served"
    else:
        reason = "Outside delivery radius"
    return {"distance_km": distance, "serviceable": serviceable, "message": reason}
