"""Public shop discovery within a map viewport; no private shop fields."""
import math

import frappe

from local_commerce.services.locations import map_config
from local_commerce.services.orders import SHOP_LISTING_FIELDS, serialize_public_shop
from local_commerce.services.owner import reject


def viewport(south, west, north, east):
    try:
        south, west, north, east = map(float, (south, west, north, east))
        if not all(math.isfinite(n) for n in (south, west, north, east)):
            raise ValueError
        if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
            raise ValueError
    except (TypeError, ValueError):
        reject("Choose a valid map area")
    return south, west, north, east


def shops(south, west, north, east):
    south, west, north, east = viewport(south, west, north, east)
    rows = frappe.get_all(
        "LC Shop", filters=[
            ["status", "=", "Active"],
            ["latitude", ">=", south], ["latitude", "<=", north],
            ["longitude", ">=", west], ["longitude", "<=", east],
        ],
        fields=SHOP_LISTING_FIELDS, order_by="shop_name asc, name asc", limit_page_length=501,
    )
    return {"shops": [shop for row in rows[:500]
                      if (shop := serialize_public_shop(row)).get("location")],
            "has_more": len(rows) > 500, "map": map_config()}
