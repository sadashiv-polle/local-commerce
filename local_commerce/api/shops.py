import frappe

from local_commerce.services import shops


@frappe.whitelist()
def list_shops(start=0, page_length=20):
    return shops.list_shops(start, page_length)


@frappe.whitelist()
def get_shop(shop):
    return shops.get_shop(shop)


@frappe.whitelist(methods=["POST"])
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
    return shops.update_shop(
        shop,
        shop_name,
        status,
        description,
        address_line1,
        city,
        postal_code,
        latitude,
        longitude,
        service_radius_km,
        live_tracking_enabled,
    )
