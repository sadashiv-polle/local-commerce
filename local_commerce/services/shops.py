import frappe

from local_commerce.permissions.scope import require_platform, require_shop
from local_commerce.services.location_rules import point
from local_commerce.services.locations import map_config, shop_location
from local_commerce.services.owner import checked_number, reject


def list_shops(start=0, page_length=20):
    start, page_length = int(start), int(page_length)
    if start < 0 or not 1 <= page_length <= 100:
        frappe.throw("Invalid pagination")
    return frappe.get_list(
        "LC Shop",
        fields=["name", "shop_name", "company", "status"],
        start=start,
        page_length=page_length,
        order_by="shop_name asc, name asc",
    )


def get_shop(shop):
    require_shop(shop)
    doc = frappe.get_doc("LC Shop", shop)
    doc.check_permission("read")
    result = {
        key: doc.get(key)
        for key in (
            "name",
            "shop_name",
            "company",
            "status",
            "description",
            "address_line1",
            "city",
            "postal_code",
            "latitude",
            "longitude",
            "service_radius_km",
            "live_tracking_enabled",
        )
    }
    result["location"] = shop_location(doc)
    result["map"] = map_config()
    return result


def update_shop(
    shop,
    shop_name,
    status,
    description="",
    address_line1=None,
    city=None,
    postal_code=None,
    latitude=None,
    longitude=None,
    service_radius_km=None,
    live_tracking_enabled=None,
):
    require_shop(shop, "write")
    doc = frappe.get_doc("LC Shop", shop)
    doc.shop_name, doc.status, doc.description = shop_name, status, description
    if address_line1 is not None:
        require_platform()
        try:
            location = point(latitude, longitude)
        except ValueError as exc:
            reject(str(exc))
        address_line1 = str(address_line1 or "").strip()
        city = str(city or "").strip()
        postal_code = str(postal_code or "").strip().upper()
        if any(len(value) > 140 for value in (address_line1, city, postal_code)):
            reject("Shop address is too long")
        if location and not all((address_line1, city, postal_code)):
            reject("Enter the complete shop address before saving its map location")
        radius = checked_number(
            service_radius_km if service_radius_km not in (None, "") else 5,
            "Delivery radius",
            positive=True,
        )
        doc.update(
            {
                "address_line1": address_line1,
                "city": city,
                "postal_code": postal_code,
                "latitude": location["latitude"] if location else None,
                "longitude": location["longitude"] if location else None,
                "service_radius_km": float(radius),
                "live_tracking_enabled": live_tracking_enabled in (True, 1, "1", "true", "True"),
            }
        )
    doc.save()
    return get_shop(shop)
