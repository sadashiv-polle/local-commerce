import frappe

from local_commerce.services import shops


@frappe.whitelist()
def list_shops(start=0, page_length=20):
    return shops.list_shops(start, page_length)


@frappe.whitelist()
def get_shop(shop):
    return shops.get_shop(shop)


@frappe.whitelist(methods=["POST"])
def update_hours(shop, accepting_orders, opening_hours):
    return shops.update_hours(shop, accepting_orders, opening_hours)


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
    order_response_minutes=10,
    accepting_orders=1,
    opening_hours=None,
    minimum_order_amount=None,
    free_delivery_above=None,
    delivery_fee_per_km=None,
    delivery_included_km=None,
    delivery_fee=None,
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
        order_response_minutes,
        accepting_orders,
        opening_hours,
        minimum_order_amount,
        free_delivery_above,
        delivery_fee_per_km,
        delivery_included_km,
        delivery_fee,
    )
