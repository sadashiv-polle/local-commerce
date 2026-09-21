"""Delivery orders backed by ERPNext Sales Orders and Delivery Notes; no online payment."""

import hashlib
import hmac
import json
from contextvars import ContextVar
from html import escape

import frappe
from frappe.utils import add_to_date, getdate, now_datetime, nowdate, time_diff_in_seconds

from local_commerce.permissions.policy import can_access_shop
from local_commerce.permissions.scope import identity, memberships, require_shop, shop_query
from local_commerce.services import notifications as order_notifications
from local_commerce.services import order_rules, scheduled
from local_commerce.services.delivery_pricing import delivery_price
from local_commerce.services.location_rules import (
    accuracy_metres,
    delivery_match,
    distance_km,
    point,
)
from local_commerce.services.locations import map_config, shop_location
from local_commerce.services.owner import (
    _owner_operation,
    balance,
    checked_number,
    company_link,
    get_price,
    reject,
)
from local_commerce.services.product_images import gallery_urls
from local_commerce.services.reorder_rules import reorder_line
from local_commerce.services.selling_rules import selected as selected_offer
from local_commerce.services.selling_rules import stock_weight_matches
from local_commerce.services.shop_hours import availability as shop_availability

_order_operation = ContextVar("lc_order_operation", default=False)
_DELIVERY_OTP_ATTEMPTS = 5
_DELIVERY_OTP_LOCK_SECONDS = 300


def delivery_otp(doc):
    """Return an order-specific OTP without storing or emailing the raw code."""
    secret = str(frappe.conf.get("encryption_key") or "")
    if not secret:
        reject("Delivery confirmation is not configured securely; contact the administrator")
    payload = f"local-commerce-delivery:{doc.name}:{doc.customer_user}:{doc.request_hash}"
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def verify_delivery_otp(doc, supplied):
    attempt_key = (
        "lc-delivery-otp-attempts:"
        + hashlib.sha256(f"{doc.name}:{doc.delivery_user}".encode()).hexdigest()
    )
    lock_key = attempt_key + ":lock"
    with frappe.cache.lock(lock_key, timeout=10, blocking_timeout=3):
        attempts = int(frappe.cache.get_value(attempt_key) or 0)
        if attempts >= _DELIVERY_OTP_ATTEMPTS:
            reject("Too many incorrect OTP attempts. Wait 5 minutes and try again")
        value = str(supplied or "").strip()
        if (
            len(value) != 6
            or not value.isdigit()
            or not hmac.compare_digest(value, delivery_otp(doc))
        ):
            attempts += 1
            frappe.cache.set_value(attempt_key, attempts, expires_in_sec=_DELIVERY_OTP_LOCK_SECONDS)
            remaining = _DELIVERY_OTP_ATTEMPTS - attempts
            suffix = (
                f" {remaining} attempt{'s' if remaining != 1 else ''} remaining."
                if remaining
                else " Wait 5 minutes before trying again."
            )
            reject("Incorrect delivery OTP." + suffix)
        frappe.cache.delete_value(attempt_key)


def customer_access():
    if frappe.session.user == "Guest":
        frappe.throw("Please sign in to place an order", frappe.AuthenticationError)
    return frappe.session.user


def is_shop_driver(user, shop):
    return (
        isinstance(user, str)
        and bool(user)
        and user != "Guest"
        and "LC Delivery Person" in frappe.get_roles(user)
        and bool(
            frappe.db.exists(
                "LC Shop Member",
                {"shop": shop, "user": user, "membership_role": "Delivery Person", "enabled": 1},
            )
        )
    )


def default_delivery_account(company):
    account = frappe.db.get_value("Company", company, "default_income_account")
    filters = {"company": company, "is_group": 0, "disabled": 0}
    if account and frappe.db.exists("Account", {"name": account, **filters}):
        return account
    return frappe.db.get_value("Account", {**filters, "root_type": "Income"}, "name")


def validate_delivery(doc, method=None):
    response_minutes = checked_number(
        doc.order_response_minutes or 10, "Order response time", positive=True
    )
    if response_minutes != response_minutes.to_integral_value() or response_minutes > 120:
        reject("Enter a whole order response time from 1 to 120 minutes")
    doc.order_response_minutes = int(response_minutes)
    try:
        location = point(doc.latitude, doc.longitude)
    except ValueError as exc:
        reject(str(exc))
    if location:
        if not all((doc.address_line1, doc.city, doc.postal_code)):
            reject("Enter the complete shop address for its map location")
        checked_number(doc.service_radius_km, "Delivery radius", positive=True)
    if doc.cod_enabled:
        company_link(
            "Account",
            doc.cod_cash_account,
            doc.company,
            {"is_group": 0, "disabled": 0, "account_type": "Cash"},
        )
        if not doc.cod_mode_of_payment or not frappe.db.exists(
            "Mode of Payment", {"name": doc.cod_mode_of_payment, "type": "Cash"}
        ):
            reject("Select a valid cash Mode of Payment")
    if not doc.delivery_enabled and not doc.get("scheduled_enabled"):
        return
    if not location:
        reject("Set the shop location on the map before enabling delivery")
    if not doc.warehouse or not doc.selling_price_list:
        reject("Set warehouse and selling price list before enabling delivery")
    company_link("Warehouse", doc.warehouse, doc.company, {"is_group": 0, "disabled": 0})
    if doc.order_tax_template and not frappe.db.exists(
        "Sales Taxes and Charges Template",
        {
            "name": doc.order_tax_template,
            "company": doc.company,
            "disabled": 0,
        },
    ):
        reject("Select an order tax template belonging to the shop Company")
    fee = checked_number(doc.delivery_fee or 0, "Delivery fee")
    for field in (
        "minimum_order_amount",
        "free_delivery_above",
        "delivery_fee_per_km",
        "delivery_included_km",
    ):
        checked_number(doc.get(field) or 0, field.replace("_", " "))
    if fee or doc.delivery_fee_per_km:
        if not doc.delivery_account:
            doc.delivery_account = default_delivery_account(doc.company)
        if not doc.delivery_account:
            reject("Select a delivery charge account belonging to the shop Company")
        company_link("Account", doc.delivery_account, doc.company, {"is_group": 0, "disabled": 0})


def public_shop(name, browsing=False, scheduled_delivery=False):
    doc = frappe.get_doc("LC Shop", name)
    enabled = doc.get("scheduled_enabled") if scheduled_delivery else doc.delivery_enabled
    if doc.status != "Active" or (not browsing and not enabled):
        reject("This shop is not accepting delivery requests")

    hours = shop_availability(doc)
    if not browsing and not scheduled_delivery and not hours["open"]:
        reject(hours["message"])
    if not browsing:
        validate_delivery(doc)
    return doc


SHOP_LISTING_FIELDS = [
    "name",
    "shop_name",
    "description",
    "address_line1",
    "city",
    "latitude",
    "longitude",
    "delivery_enabled",
    "scheduled_enabled",
    "cod_enabled",
    "accepting_orders",
    "opening_hours_json",
]


def serialize_public_shop(row):
    try:
        row.location = point(row.latitude, row.longitude)
    except ValueError:
        row.location = None
    row.pop("latitude", None)
    row.pop("longitude", None)
    hours = shop_availability(row)
    row.availability = hours
    row.accepting_orders = bool(
        (row.delivery_enabled and hours["open"] or row.get("scheduled_enabled"))
        and row.cod_enabled and row.location
    )
    for internal in ("delivery_enabled", "cod_enabled", "opening_hours_json"):
        row.pop(internal, None)
    return row


def shops(start=0):
    rows = frappe.get_all(
        "LC Shop",
        filters={"status": "Active"},
        fields=SHOP_LISTING_FIELDS,
        start=offset(start),
        limit_page_length=20,
    )
    return [serialize_public_shop(row) for row in rows]


def nearby_shops(address, start=0):
    start = offset(start)
    try:
        destination = point(address.get("latitude"), address.get("longitude"), required=True)
    except ValueError as exc:
        reject(str(exc))
    rows = frappe.get_all(
        "LC Shop",
        filters={"status": "Active"},
        fields=[
            *SHOP_LISTING_FIELDS,
            "service_radius_km",
        ],
        limit_page_length=1001,
    )
    if len(rows) > 1000:
        reject("Nearby discovery is temporarily unavailable; too many shops need indexing")
    result = []
    for row in rows:
        radius = float(row.service_radius_km or 0)
        public = serialize_public_shop(row)
        location = public.location
        match = delivery_match(location, destination, radius, public.accepting_orders)
        public.update(
            {
                "distance_km": match["distance_km"],
                "service_radius_km": radius,
                "serviceable": match["serviceable"],
                "serviceability_message": match["message"],
            }
        )
        result.append(public)
    result.sort(
        key=lambda row: (
            not row.serviceable,
            row.distance_km is None,
            row.distance_km if row.distance_km is not None else float("inf"),
            row.shop_name.lower(),
        )
    )
    page = result[start : start + 20]
    return {
        "address": address,
        "shops": page,
        "has_more": len(result) > start + 20,
        "map": map_config(),
    }


def offset(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        reject("Invalid page")
    if value < 0:
        reject("Invalid page")
    return value


def product_data(shop, item, browsing=False):
    if (
        item.lc_shop != shop.name
        or item.disabled
        or (item.lc_sold_out and not browsing)
        or not item.is_stock_item
    ):
        reject("A product is no longer available")
    if item.has_batch_no or item.has_serial_no or item.has_variants or item.variant_of:
        reject("This product cannot be ordered online yet")
    price = get_price(shop, item)
    today = getdate(nowdate())
    if (
        not price
        or (price.valid_from and getdate(price.valid_from) > today)
        or (price.valid_upto and getdate(price.valid_upto) < today)
    ):
        if not browsing:
            reject("A product has no current selling price")
        price = None
    currency = frappe.db.get_value("Company", shop.company, "default_currency")
    if price and price.currency != currency:
        reject("Product currency does not match this shop")
    images = gallery_urls(
        item.image,
        frappe.get_all(
            "File",
            filters={"attached_to_doctype": "Item", "attached_to_name": item.name,
                     "is_private": 0, "is_folder": 0},
            pluck="file_url",
            order_by="creation asc, name asc",
            limit_page_length=0,
        ) if browsing else [],
    )
    from local_commerce.services import fish

    available_stock = 0 if item.lc_sold_out else balance(item.name, shop.warehouse)["available"]
    return {
        "item": item.name,
        "item_name": item.item_name,
        "item_group": item.item_group,
        "image": images[0] if images else "",
        "images": images,
        "uom": item.stock_uom,
        "description": item.lc_description or "",
        "rate": float(checked_number(price.price_list_rate, "Price")) if price else None,
        "currency": currency,
        "available": fish.sellable(shop, item, available_stock),
        "preweighed_weights": fish.enabled(shop, item),
        "fixed_piece_pricing": fish.enabled(shop, item) and item.stock_uom == "Nos",
        "selling_options": [row for row in fish.selling_options(
            shop, item, frappe.parse_json(item.get("lc_selling_options") or "[]")
        ) if row.get("enabled", True)],
    }


def search_products(search, start=0, latitude=None, longitude=None, category=""):
    search = str(search or "").strip()[:140]
    start = offset(start)
    category = str(category or "").strip()[:140]
    if len(search) < 2 and not category:
        return {"items": [], "has_more": False}
    try:
        destination = point(latitude, longitude)
    except ValueError as exc:
        reject(str(exc))
    rows = frappe.get_all("LC Shop", filters={"status": "Active"},
                          fields=[*SHOP_LISTING_FIELDS, "service_radius_km"],
                          limit_page_length=1001)
    if len(rows) > 1000:
        reject("Too many shops for product search; please search inside a shop")
    public_shops = {}
    for row in rows:
        public = serialize_public_shop(row)
        match = delivery_match(public.location, destination, float(public.service_radius_km or 0),
                               public.accepting_orders) if destination else None
        public_shops[public.name] = {"shop": public.name, "shop_name": public.shop_name,
            "accepting_orders": public.accepting_orders,
            "distance_km": match["distance_km"] if match else None,
            "serviceable": match["serviceable"] if match else None,
            "serviceability_message": match["message"] if match else
                "Choose a delivery address to check availability"}
    if not public_shops:
        return {"items": [], "has_more": False}
    filters = {"lc_shop": ["in", list(public_shops)],
        "disabled": 0, "is_stock_item": 1, "has_batch_no": 0, "has_serial_no": 0,
        "has_variants": 0, "variant_of": ["is", "not set"]}
    if category:
        filters["item_group"] = category
    candidates = frappe.get_all("Item", filters=filters,
        or_filters={"item_name": ["like", f"%{search}%"], "name": ["like", f"%{search}%"]}
        if search else None,
        fields=["name", "lc_shop", "item_name"], limit_page_length=2001)
    if len(candidates) > 2000:
        reject("Too many matching items. Try a more specific product name")
    candidates.sort(key=lambda item: (
        public_shops[item.lc_shop]["serviceable"] is False,
        public_shops[item.lc_shop]["distance_km"] is None,
        public_shops[item.lc_shop]["distance_km"] or 0,
        item.item_name.lower(), item.name))
    items, shop_docs = [], {}
    for row in candidates[start:start + 20]:
        if row.lc_shop not in shop_docs:
            shop_docs[row.lc_shop] = public_shop(row.lc_shop, browsing=True)
        product = product_data(
            shop_docs[row.lc_shop], frappe.get_doc("Item", row.name), browsing=True
        )
        items.append({**product, **public_shops[row.lc_shop]})
    return {"items": items, "has_more": len(candidates) > start + 20}


def public_product(shop, item):
    doc = public_shop(shop, browsing=True)
    return product_data(doc, frappe.get_doc("Item", item), browsing=True)


def catalog(shop, start=0, search="", category="", in_stock=0):
    doc = public_shop(shop, browsing=True)
    location = shop_location(doc)
    start = offset(start)
    search = str(search or "").strip()[:140]
    category = str(category or "").strip()[:140]
    only_stock = in_stock in (True, 1, "1", "true", "True")
    filters = {
        "lc_shop": shop,
        "disabled": 0,
        "is_stock_item": 1,
        "has_batch_no": 0,
        "has_serial_no": 0,
        "has_variants": 0,
        "variant_of": ["is", "not set"],
    }
    # Categories belong to this shop's public catalogue, not the current page.
    categories = sorted(set(frappe.get_all(
        "Item", filters=filters, pluck="item_group", limit_page_length=0
    )) - {None, ""})
    if category:
        filters["item_group"] = category
    names = frappe.get_all(
        "Item",
        filters=filters,
        or_filters={"item_name": ["like", f"%{search}%"], "name": ["like", f"%{search}%"]}
        if search else None,
        pluck="name",
        start=0 if only_stock else start,
        limit_page_length=0 if only_stock else 21,
        order_by="item_name asc, name asc",
    )
    products = []
    matched = 0
    for name in names:
        item = frappe.get_doc("Item", name)
        product = product_data(doc, item, browsing=True)
        if only_stock:
            if product["available"] <= 0 or product["rate"] is None:
                continue
            matched += 1
            if matched <= start:
                continue
        products.append(product)
        if len(products) == 21:
            break
    has_more = len(products) > 20
    products = products[:20]
    hours = shop_availability(doc)
    return {
        "shop_name": doc.shop_name,
        "shop_location": location,
        "map": map_config(),
        "accepting_orders": bool(
            (doc.delivery_enabled and hours["open"] or doc.get("scheduled_enabled"))
            and doc.cod_enabled and location
        ),
        "availability": hours,
        "normal_enabled": bool(doc.delivery_enabled),
        "scheduled_enabled": bool(doc.get("scheduled_enabled")),
        "delivery_slots": scheduled.slots(doc.name),
        "timezone": frappe.utils.get_system_timezone(),
        "items": products,
        "has_more": has_more,
        "categories": categories,
        "delivery_fee": doc.delivery_fee or 0,
        "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
        "payment_methods": ["Cash on Delivery"] if doc.cod_enabled else [],
        "payment_message": (
            "Pay the rider when your order arrives"
            if doc.cod_enabled
            else "This shop is setting up customer payments"
        ),
    }


def pricing_for(shop, subtotal, distance, delivery_mode="Normal"):
    if delivery_mode == "Scheduled":
        return delivery_price(subtotal, base=0, per_km=0, included_km=0, distance=distance,
                              minimum=shop.minimum_order_amount, free_above=0)
    return delivery_price(
        subtotal,
        base=shop.delivery_fee,
        per_km=shop.delivery_fee_per_km,
        included_km=shop.delivery_included_km,
        distance=distance,
        minimum=shop.minimum_order_amount,
        free_above=shop.free_delivery_above,
    )


def quote(shop, items, latitude=None, longitude=None, delivery_mode="Normal",
          scheduled_slot=None):
    doc = public_shop(shop, browsing=True)
    try:
        rows = order_rules.cart_rows(frappe.parse_json(items))
        destination = point(latitude, longitude)
    except (ValueError, TypeError) as exc:
        reject(str(exc))
    origin = shop_location(doc)
    distance = distance_km(origin, destination) if origin and destination else None
    subtotal = checked_number(0, "Subtotal")
    for row in rows:
        product = product_data(doc, frappe.get_doc("Item", row["item"]))
        quantity, snapshot = selling_quantity(product, row)
        subtotal += (checked_number(snapshot["fixed_amount"], "Piece total")
                     if snapshot.get("billing") == "Pieces"
                     else quantity * checked_number(product["rate"], "Price"))
    scheduled.validate_booking(doc, delivery_mode, scheduled_slot, rows)
    price = pricing_for(doc, subtotal, distance, delivery_mode)
    price.update({"subtotal": float(subtotal), "distance_km": distance})
    return price


def selling_quantity(product, row):
    offers = product.get("selling_options") or []
    if offers or row.get("option_id"):
        if product["uom"] != "Kg":
            reject("Packed-weight products must use Kg as their stock unit")
        try:
            offer = selected_offer(offers, row.get("option_id"), row["quantity"])
        except ValueError as exc:
            reject(str(exc))
        snapshot = {"item": product["item"], "option_id": offer["id"],
                    "label": offer["label"], "kind": offer["kind"],
                    "option_quantity": offer["quantity"], "packs": offer["packs"],
                    "estimated_weight": offer["estimated_total_weight"],
                    "actual_weight": (offer["estimated_total_weight"]
                                      if product.get("preweighed_weights")
                                      and offer["kind"] == "Weight" else None),
                    "preweighed": bool(product.get("preweighed_weights")
                                       and offer["kind"] == "Weight"),
                    "rate_per_kg": product["rate"],
                    "billing": offer["billing"], "piece_price": offer["piece_price"]}
        snapshot["fixed_amount"] = (float(checked_number(offer["piece_price"], "Price")
                                          * checked_number(offer["quantity"], "Pieces")
                                          * checked_number(offer["packs"], "Packs"))
                                    if offer["billing"] == "Pieces" else None)
        return checked_number(offer["estimated_total_weight"], "Estimated weight",
                              positive=True), snapshot
    return checked_number(row["quantity"], "Quantity", positive=True), {}


def customer_record(user, company):
    from local_commerce.services.customers import ensure_customer

    if user != frappe.session.user:
        frappe.throw("Customer access denied", frappe.PermissionError)
    return ensure_customer()["name"]


def place(shop, items, address, request_key, payment_method="Cash on Delivery",
          delivery_mode="Normal", scheduled_slot=None):
    user = customer_access()
    try:
        rows = order_rules.cart_rows(frappe.parse_json(items))
        address = order_rules.address_fields(frappe.parse_json(address))
    except (ValueError, TypeError) as exc:
        reject(str(exc))
    if not isinstance(request_key, str) or not 16 <= len(request_key) <= 100:
        reject("Invalid request key")
    key = hashlib.sha256(f"{user}:{shop}:{request_key}".encode()).hexdigest()
    if payment_method != "Cash on Delivery":
        reject("Select a supported payment method")
    digest = hashlib.sha256(
        json.dumps([rows, address, payment_method] + (
            [delivery_mode, scheduled_slot] if delivery_mode != "Normal" else []
        ), sort_keys=True).encode()
    ).hexdigest()
    legacy_digest = hashlib.sha256(json.dumps([rows, address], sort_keys=True).encode()).hexdigest()
    # Same lock order as owner stock operations. One shop's checkout is serialized.
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", shop)
    previous = frappe.db.get_value(
        "LC Order", {"request_key": key}, ["name", "request_hash"], as_dict=True
    )
    if previous:
        if previous.request_hash != digest and not (
            delivery_mode == "Normal" and previous.request_hash == legacy_digest
        ):
            reject("This request key was already used for another order")
        return detail(previous.name)
    doc = public_shop(shop, scheduled_delivery=delivery_mode == "Scheduled")
    slot = scheduled.validate_booking(doc, delivery_mode, scheduled_slot, rows, address)
    if not doc.cod_enabled:
        reject("Cash on Delivery is not configured for this shop")
    origin = shop_location(doc)
    destination = point(address["latitude"], address["longitude"])
    delivery_distance = None
    if origin:
        if not destination:
            reject("Select your delivery location on the map")
        delivery_distance = distance_km(origin, destination)
        if delivery_mode == "Normal" and delivery_distance > float(
            checked_number(doc.service_radius_km, "Delivery radius", positive=True)
        ):
            reject(
                f"This address is {delivery_distance:g} km away and outside the shop delivery area"
            )
    prepared, selling_lines, item_totals = [], [], {}
    for row in rows:
        item = frappe.get_doc("Item", row["item"])
        product = product_data(doc, item)
        quantity, snapshot = selling_quantity(product, row)
        selling_lines.append(snapshot)
        try:
            order_rules.whole_quantity(
                quantity, frappe.db.get_value("UOM", item.stock_uom, "must_be_whole_number")
                or (doc.get("shop_type") == "Fish" and item.stock_uom == "Nos")
            )
        except ValueError as exc:
            reject(str(exc))
        item_totals[item.name] = item_totals.get(item.name, 0) + quantity
        if item_totals[item.name] > checked_number(
            balance(item.name, doc.warehouse, lock=True)["available"], "Available stock"
        ):
            reject("Not enough available stock; update your cart")
        by_piece = snapshot.get("billing") == "Pieces"
        sale_qty = snapshot["option_quantity"] * snapshot["packs"] if by_piece else float(quantity)
        sale_rate = snapshot["piece_price"] if by_piece else product["rate"]
        prepared.append(
            {
                "item_code": item.name,
                "item_name": item.item_name,
                "qty": sale_qty,
                "rate": sale_rate,
                "price_list_rate": sale_rate,
                "uom": "Nos" if by_piece else item.stock_uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": float(quantity) / sale_qty if by_piece else 1,
                "warehouse": doc.warehouse,
                "delivery_date": getdate(slot.delivery_start) if slot else nowdate(),
                "description": escape(item.item_name + (
                    f" · {snapshot['label']} × {snapshot['packs']:g}; "
                    + ("pre-weighed pack" if snapshot.get("preweighed") else "estimated weight, "
                    + ("fixed piece price" if snapshot.get("billing") == "Pieces"
                     else "final price after packing")) if snapshot else ""
                )),
            }
        )
    price = pricing_for(
        doc,
        sum(
            checked_number(row["qty"], "Quantity") * checked_number(row["rate"], "Price")
            for row in prepared
        ),
        delivery_distance, delivery_mode,
    )
    if price["minimum_remaining"]:
        reject(f"Add {price['minimum_remaining']:g} more to meet the shop minimum order amount")
    if price["needs_location"]:
        reject("Select your delivery location to calculate the delivery fee")
    token = _order_operation.set(True)
    owner_token = _owner_operation.set(True)
    try:
        order = frappe.get_doc(
            {
                "doctype": "LC Order",
                "request_key": key,
                "request_hash": digest,
                "selling_lines_json": json.dumps(selling_lines),
                "shop": shop,
                "customer_user": user,
                "status": "Requested",
                "delivery_mode": delivery_mode,
                "scheduled_slot": slot.name if slot else None,
                "payment_method": payment_method,
                "payment_status": "Pending",
                "recipient": address["recipient"],
                "phone": address["phone"],
                "address_snapshot": json.dumps(address),
                "destination_latitude": address["latitude"],
                "destination_longitude": address["longitude"],
                "delivery_distance_km": delivery_distance,
                "delivery_instructions": address["delivery_instructions"],
            }
        ).insert(ignore_permissions=True)
        customer = customer_record(user, doc.company)
        destination = frappe.get_doc(
            {
                "doctype": "Address",
                "address_title": order.name,
                "address_type": "Shipping",
                "address_line1": address["line1"],
                "city": address["city"],
                "pincode": address["postal_code"],
                "phone": address["phone"],
                "country": frappe.db.get_value("Company", doc.company, "country"),
                # ERPNext v15 Address validation expects this value even on sites where
                # the optional Custom Field is missing from Address metadata.
                "is_your_company_address": 0,
                "is_shipping_address": 1,
                "links": [{"link_doctype": "Customer", "link_name": customer}],
            }
        )
        destination.is_your_company_address = 0
        destination.insert(ignore_permissions=True)
        so = frappe.get_doc(
            {
                "doctype": "Sales Order",
                "lc_order": order.name,
                "company": doc.company,
                "customer": customer,
                "transaction_date": nowdate(),
                "delivery_date": getdate(slot.delivery_start) if slot else nowdate(),
                "order_type": "Sales",
                "selling_price_list": doc.selling_price_list,
                "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
                "conversion_rate": 1,
                "plc_conversion_rate": 1,
                "ignore_pricing_rule": 1,
                "shipping_address_name": destination.name,
                "set_warehouse": doc.warehouse,
                "taxes_and_charges": doc.order_tax_template,
                "items": prepared,
                "remarks": "Delivery timing requires shop confirmation. No payment collected.",
            }
        )
        from erpnext.controllers.accounts_controller import get_taxes_and_charges

        if doc.order_tax_template:
            so.set(
                "taxes",
                get_taxes_and_charges("Sales Taxes and Charges Template", doc.order_tax_template),
            )
        so.flags.ignore_permissions = True
        so.set_missing_values()
        if price["delivery_fee"]:
            so.append(
                "taxes",
                {
                    "charge_type": "Actual",
                    "account_head": doc.delivery_account,
                    "description": "Delivery charge",
                    "tax_amount": price["delivery_fee"],
                },
            )
        so.insert(ignore_permissions=True)
        for expected, posted in zip(prepared, so.items, strict=True):
            if checked_number(posted.qty, "Quantity") != checked_number(
                expected["qty"], "Quantity"
            ):
                reject("ERPNext quantity precision changed this order; use a supported quantity")
        for snapshot, posted in zip(selling_lines, so.items, strict=True):
            if snapshot.get("billing") == "Pieces":
                if not stock_weight_matches(
                    posted.stock_qty, snapshot["estimated_weight"], posted.qty,
                    posted.precision("stock_qty"), posted.precision("conversion_factor"),
                ):
                    reject("ERPNext stock precision changed this option; use a supported weight")
                if frappe.utils.flt(posted.amount, posted.precision("amount")) != frappe.utils.flt(
                    snapshot["fixed_amount"], posted.precision("amount")
                ):
                    reject("ERPNext changed this piece price; contact the administrator")
        from local_commerce.services import fish

        fish.reserve(order, so.items)
        order.sales_order = so.name
        order.save(ignore_permissions=True)
        order_notifications.order_created(order)
        return detail(order.name)
    finally:
        _owner_operation.reset(owner_token)
        _order_operation.reset(token)


def authorize(doc, write=False):
    if not write and doc.customer_user == frappe.session.user and frappe.session.user != "Guest":
        return
    if (
        not write
        and doc.delivery_user == frappe.session.user
        and is_shop_driver(frappe.session.user, doc.shop)
    ):
        return
    require_shop(doc.shop, "write" if write else "read")


def serialize(doc):
    so = frappe.get_doc("Sales Order", doc.sales_order)
    selling_lines = json.loads(doc.get("selling_lines_json") or "[]")
    estimated = any(line.get("option_id") and line.get("actual_weight") is None
                    for line in selling_lines)
    shop = frappe.get_doc("LC Shop", doc.shop)
    try:
        destination_location = point(doc.destination_latitude, doc.destination_longitude)
    except ValueError:
        destination_location = None
    try:
        driver_location = (
            point(doc.driver_latitude, doc.driver_longitude)
            if doc.status == "Out for Delivery" and doc.driver_location_at
            else None
        )
    except ValueError:
        driver_location = None
    is_customer = frappe.session.user != "Guest" and doc.customer_user == frappe.session.user
    response_start = (frappe.db.get_value("LC Delivery Slot", doc.scheduled_slot, "ordering_end")
                      if doc.get("scheduled_slot") else doc.creation)
    response_deadline = add_to_date(response_start, minutes=int(shop.order_response_minutes or 10))
    return {
        "name": doc.name,
        "modified": str(doc.modified),
        "estimated": estimated,
        "delivery_mode": doc.get("delivery_mode") or "Normal",
        "scheduled_slot": doc.get("scheduled_slot"),
        "scheduled_period": (frappe.db.get_value("LC Delivery Slot", doc.scheduled_slot,
            ["title", "delivery_start", "delivery_end"], as_dict=True)
            if doc.get("scheduled_slot") else None),
        "selling_lines": selling_lines,
        "shop": doc.shop,
        "shop_name": frappe.db.get_value("LC Shop", doc.shop, "shop_name"),
        "status": doc.status,
        "created": str(doc.creation),
        "response_deadline": str(response_deadline),
        "response_seconds_remaining": max(
            0, int(time_diff_in_seconds(response_deadline, now_datetime()))
        ),
        "recipient": doc.recipient,
        "phone": doc.phone,
        "address": json.loads(doc.address_snapshot),
        "destination_location": destination_location,
        "delivery_distance_km": doc.delivery_distance_km,
        "delivery_instructions": doc.delivery_instructions,
        "shop_location": shop_location(shop),
        "map": map_config(),
        "live_tracking_enabled": bool(shop.live_tracking_enabled),
        "driver_location": (
            {
                **driver_location,
                "accuracy": doc.driver_location_accuracy,
                "updated_at": str(doc.driver_location_at),
            }
            if driver_location
            else None
        ),
        "reason": doc.reason,
        "delivery_user": doc.delivery_user,
        "delivery_name": (
            frappe.db.get_value("User", doc.delivery_user, "full_name")
            if doc.delivery_user
            else None
        ),
        "assigned_at": str(doc.assigned_at) if doc.assigned_at else None,
        "picked_up_at": str(doc.picked_up_at) if doc.picked_up_at else None,
        "delivered_at": str(doc.delivered_at) if doc.delivered_at else None,
        "payment_method": doc.payment_method,
        "payment_status": doc.payment_status,
        "sales_invoice": doc.sales_invoice,
        "payment_entry": doc.payment_entry,
        "delivery_otp": (
            delivery_otp(doc) if is_customer and doc.status == "Out for Delivery" else None
        ),
        "collected_at": str(doc.collected_at) if doc.collected_at else None,
        "currency": so.currency,
        "total": so.grand_total,
        "taxes_and_charges": so.total_taxes_and_charges,
        "erp_status": so.status,
        "items": [
            {
                "name": i.item_name,
                "quantity": i.qty,
                "uom": i.uom,
                "rate": i.rate,
                "amount": i.amount,
            }
            for i in so.items
        ],
    }


def detail(order):
    doc = frappe.get_doc("LC Order", order)
    authorize(doc)
    return serialize(doc)


def reorder_preview(order):
    doc = frappe.get_doc("LC Order", order)
    if frappe.session.user == "Guest" or doc.customer_user != frappe.session.user:
        frappe.throw("Only the customer can reorder this order", frappe.PermissionError)
    if doc.status not in {"Delivered", "Cancelled"}:
        reject("Order again is available after delivery or cancellation")
    shop = public_shop(doc.shop, browsing=True)
    so = frappe.get_doc("Sales Order", doc.sales_order)
    items, notices = [], []
    for row in so.items:
        product = None
        if frappe.db.exists("Item", row.item_code):
            item = frappe.get_doc("Item", row.item_code)
            if (item.lc_shop == shop.name and not item.disabled and item.is_stock_item
                    and not item.has_batch_no and not item.has_serial_no
                    and not item.has_variants and not item.variant_of):
                product = product_data(shop, item, browsing=True)
        if product and product.get("selling_options"):
            notices.append(
                f"{row.item_name}: choose your count or weight option in the shop again."
            )
            continue
        line, notice = reorder_line(
            {"name": row.item_name, "quantity": row.qty, "uom": row.uom, "rate": row.rate},
            product,
        )
        if line:
            items.append(line)
        if notice:
            notices.append(notice)
    return {"shop": shop.name, "shop_name": shop.shop_name,
            "currency": so.currency, "items": items, "notices": notices}


def delivery_route(order):
    doc = frappe.get_doc("LC Order", order)
    authorize(doc)
    if doc.status not in {"Picked Up", "Out for Delivery"}:
        reject("The delivery route appears after pickup")
    shop = frappe.get_doc("LC Shop", doc.shop)
    origin = shop_location(shop)
    try:
        destination = point(doc.destination_latitude, doc.destination_longitude, required=True)
    except ValueError as exc:
        reject(str(exc))
    if not origin:
        reject("Set the shop map location before starting delivery")
    from local_commerce.services.routing import road_route

    return road_route(origin, destination)


def list_orders(shop=None, start=0, status=None):
    if shop:
        require_shop(shop)
        filters = {"shop": shop}
    else:
        customer_access()
        filters = {"customer_user": frappe.session.user}
    if status:
        valid_statuses = set(order_rules.TRANSITIONS) | set(order_rules.DELIVERY_TRANSITIONS)
        if status not in valid_statuses:
            reject("Invalid order status")
        filters["status"] = status
    names = frappe.get_all(
        "LC Order",
        filters=filters,
        pluck="name",
        start=offset(start),
        limit_page_length=20,
        order_by="creation desc",
    )
    return [serialize(frappe.get_doc("LC Order", name)) for name in names]


def drivers(shop):
    require_shop(shop, "write")
    members = frappe.get_all(
        "LC Shop Member",
        filters={"shop": shop, "membership_role": "Delivery Person", "enabled": 1},
        pluck="user",
        order_by="user asc",
        limit_page_length=0,
    )
    result = []
    for user in members:
        if frappe.db.get_value(
            "User", user, "enabled"
        ) and "LC Delivery Person" in frappe.get_roles(user):
            result.append(
                {"user": user, "full_name": frappe.db.get_value("User", user, "full_name") or user}
            )
    return result


def payment_options(shop):
    require_shop(shop, "write")
    doc = frappe.get_doc("LC Shop", shop)
    return {
        "enabled": bool(doc.cod_enabled),
        "cash_account": doc.cod_cash_account,
        "mode_of_payment": doc.cod_mode_of_payment,
        "cash_accounts": frappe.get_all(
            "Account",
            filters={
                "company": doc.company,
                "is_group": 0,
                "disabled": 0,
                "account_type": "Cash",
            },
            pluck="name",
            order_by="name asc",
            limit_page_length=500,
        ),
        "modes": frappe.get_all(
            "Mode of Payment",
            filters={"type": "Cash"},
            pluck="name",
            order_by="name asc",
            limit_page_length=100,
        ),
    }


def configure_cod(shop, enabled, cash_account="", mode_of_payment=""):
    require_shop(shop, "write")
    doc = frappe.get_doc("LC Shop", shop)
    requested_enabled = enabled in (True, 1, "1", "true", "True")
    pending = frappe.db.count("LC COD Collection", {"shop": shop, "status": "Awaiting Handover"})
    if pending and (
        not requested_enabled
        or cash_account != doc.cod_cash_account
        or mode_of_payment != doc.cod_mode_of_payment
    ):
        reject("Reconcile all pending cash handovers before changing Cash on Delivery settings")
    doc.cod_enabled = requested_enabled
    doc.cod_cash_account = cash_account or None
    doc.cod_mode_of_payment = mode_of_payment or None
    validate_delivery(doc)
    doc.save(ignore_permissions=True)
    return payment_options(shop)


def assign_driver(order, delivery_user):
    doc = frappe.get_doc("LC Order", order)
    authorize(doc, True)
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    frappe.db.sql("select name from `tabLC Order` where name=%s for update", doc.name)
    doc.reload()
    if doc.status != "Ready":
        reject("A delivery person can only be assigned when the order is ready")
    if not is_shop_driver(delivery_user, doc.shop):
        reject("Select an enabled delivery person assigned to this shop")
    if doc.delivery_user == delivery_user:
        return serialize(doc)
    token = _order_operation.set(True)
    try:
        previous = doc.delivery_user
        doc.delivery_user = delivery_user
        doc.assigned_at = now_datetime()
        doc.save(ignore_permissions=True)
        label = frappe.db.get_value("User", delivery_user, "full_name") or delivery_user
        action = "Reassigned" if previous else "Assigned"
        doc.add_comment("Info", escape(f"{action} delivery to {label}."))
        order_notifications.driver_assigned(doc, previous)
        return serialize(doc)
    finally:
        _order_operation.reset(token)


def driver_shops(user=None):
    user = user or frappe.session.user
    if user == "Guest" or "LC Delivery Person" not in frappe.get_roles(user):
        frappe.throw("Delivery person access required", frappe.PermissionError)
    return sorted(
        {member.shop for member in memberships(user) if member.membership_role == "Delivery Person"}
    )


def delivery_profile():
    user = frappe.session.user
    shops = driver_shops(user)
    account = frappe.db.get_value(
        "User", user, ["name", "full_name", "email", "mobile_no", "user_image"], as_dict=True
    )
    assigned_shops = (
        frappe.get_all(
            "LC Shop",
            filters={"name": ["in", shops]},
            fields=["name", "shop_name", "status"],
            order_by="shop_name asc",
            limit_page_length=0,
        )
        if shops
        else []
    )
    base_filters = {"delivery_user": user, "shop": ["in", shops]}
    active_statuses = ["Ready", "Picked Up", "Out for Delivery"]
    if not shops:
        metrics = {
            "active": 0,
            "delivered": 0,
            "total": 0,
            "shops": 0,
            "awaiting_handover": 0,
        }
        cash_pending = []
    else:
        metrics = {
            "active": frappe.db.count(
                "LC Order", filters={**base_filters, "status": ["in", active_statuses]}
            ),
            "delivered": frappe.db.count(
                "LC Order", filters={**base_filters, "status": "Delivered"}
            ),
            "total": frappe.db.count("LC Order", filters=base_filters),
            "shops": len(assigned_shops),
            "awaiting_handover": frappe.db.count(
                "LC COD Collection",
                filters={
                    "delivery_user": user,
                    "shop": ["in", shops],
                    "status": "Awaiting Handover",
                },
            ),
        }
        cash_by_shop = {}
        for row in frappe.get_all(
            "LC COD Collection",
            filters={
                "delivery_user": user,
                "shop": ["in", shops],
                "status": "Awaiting Handover",
            },
            fields=["shop", "currency", "collected_amount"],
            limit_page_length=0,
        ):
            key = (row.shop, row.currency)
            cash_by_shop[key] = cash_by_shop.get(key, 0) + float(row.collected_amount)
        cash_pending = [
            {
                "shop": shop,
                "shop_name": frappe.db.get_value("LC Shop", shop, "shop_name"),
                "currency": currency,
                "amount": amount,
            }
            for (shop, currency), amount in sorted(cash_by_shop.items())
        ]
    return {
        "profile": account,
        "shops": assigned_shops,
        "metrics": metrics,
        "cash_pending": cash_pending,
    }


def delivery_assignments(start=0, view="active"):
    user = frappe.session.user
    shops = driver_shops(user)
    if not shops:
        return []
    if view not in {"active", "history"}:
        reject("Invalid delivery view")
    statuses = (
        ["Ready", "Picked Up", "Out for Delivery"]
        if view == "active"
        else ["Delivered", "Cancelled"]
    )
    names = frappe.get_all(
        "LC Order",
        filters={"delivery_user": user, "shop": ["in", shops], "status": ["in", statuses]},
        pluck="name",
        start=offset(start),
        limit_page_length=20,
        order_by="creation desc",
    )
    return [serialize(frappe.get_doc("LC Order", name)) for name in names]


def create_cod_collection(doc, collected_amount, driver_note=""):
    if doc.payment_method != "Cash on Delivery" or doc.payment_status != "Pending":
        reject("This order is not waiting for a Cash on Delivery payment")
    shop = frappe.get_doc("LC Shop", doc.shop)
    validate_delivery(shop)
    if not shop.cod_enabled:
        reject("Cash on Delivery is no longer configured; contact the shop")
    sales_order = frappe.get_doc("Sales Order", doc.sales_order)
    expected = checked_number(sales_order.grand_total, "Expected amount")
    collected = checked_number(collected_amount, "Collected amount")
    variance = collected - expected
    driver_note = str(driver_note or "").strip()
    if variance and not 3 <= len(driver_note) <= 500:
        reject("Explain a short or excess cash collection (3–500 characters)")
    if len(driver_note) > 500:
        reject("Delivery payment note cannot exceed 500 characters")
    original_user = frappe.session.user
    try:
        # ERPNext's mapper performs accounting permission checks. This trusted workflow has
        # already authorized and locked the assigned rider, so bookkeeping runs as the system.
        frappe.set_user("Administrator")
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

        invoice = make_sales_invoice(doc.sales_order, ignore_permissions=True)
        invoice.lc_order = doc.name
        invoice.flags.ignore_permissions = True
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        if checked_number(invoice.grand_total, "Invoice total") != expected:
            reject("The ERPNext invoice total changed; the shop must review this order")
    finally:
        frappe.set_user(original_user)
    collection = frappe.get_doc(
        {
            "doctype": "LC COD Collection",
            "order": doc.name,
            "shop": doc.shop,
            "delivery_user": doc.delivery_user,
            "currency": sales_order.currency,
            "expected_amount": float(expected),
            "collected_amount": float(collected),
            "variance": float(variance),
            "status": "Awaiting Handover",
            "collected_at": now_datetime(),
            "driver_note": driver_note,
        }
    ).insert(ignore_permissions=True)
    return invoice.name, collection.name


def delivery_change(order, target, collected_amount=None, note="", delivery_otp_value=""):
    doc = frappe.get_doc("LC Order", order)
    if doc.delivery_user != frappe.session.user or not is_shop_driver(
        frappe.session.user, doc.shop
    ):
        frappe.throw("This delivery is not assigned to you", frappe.PermissionError)
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    frappe.db.sql("select name from `tabLC Order` where name=%s for update", doc.name)
    doc.reload()
    if doc.delivery_user != frappe.session.user or not is_shop_driver(
        frappe.session.user, doc.shop
    ):
        frappe.throw("This delivery is no longer assigned to you", frappe.PermissionError)
    try:
        changed = order_rules.delivery_transition(doc.status, target)
    except ValueError as exc:
        reject(str(exc))
    if not changed:
        return serialize(doc)
    if target == "Out for Delivery" and doc.get("scheduled_slot"):
        from frappe.utils import get_datetime

        starts = frappe.db.get_value('LC Delivery Slot', doc.scheduled_slot, 'delivery_start')
        if now_datetime() < get_datetime(starts):
            reject('Scheduled delivery starts at ' + str(starts))
    if target == "Ready" and any(
        line.get("option_id") and line.get("actual_weight") is None
        for line in json.loads(doc.get("selling_lines_json") or "[]")
    ):
        reject("Enter and save the actual packed weights before marking this order Ready")
    token = _order_operation.set(True)
    owner_token = _owner_operation.set(True)
    try:
        if target == "Picked Up":
            from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

            if doc.delivery_note:
                reject("This order already has a delivery note")
            original_user = frappe.session.user
            try:
                # The assigned rider is authorized above. ERPNext's mapper separately
                # requires accounting create permission, so trusted bookkeeping runs as system.
                frappe.set_user("Administrator")
                delivery_note = make_delivery_note(doc.sales_order)
                delivery_note.lc_order = doc.name
                delivery_note.flags.ignore_permissions = True
                delivery_note.insert(ignore_permissions=True)
                from local_commerce.services import fish

                fish.validate_order(doc)
                delivery_note.submit()
                fish.picked_up(doc, delivery_note)
            finally:
                frappe.set_user(original_user)
            doc.delivery_note = delivery_note.name
            doc.picked_up_at = now_datetime()
        elif target == "Delivered":
            if (
                not doc.delivery_note
                or frappe.db.get_value("Delivery Note", doc.delivery_note, "docstatus") != 1
            ):
                reject("The submitted delivery note is missing; contact the shop")
            verify_delivery_otp(doc, delivery_otp_value)
            invoice, collection = create_cod_collection(doc, collected_amount, note)
            doc.sales_invoice = invoice
            doc.payment_status = "Collected"
            doc.collected_at = now_datetime()
            doc.delivered_at = now_datetime()
            # Precise rider coordinates are transient and are not retained after delivery.
            doc.driver_latitude = None
            doc.driver_longitude = None
            doc.driver_location_accuracy = None
            doc.driver_location_at = None
        previous = doc.status
        doc.status = target
        doc.save(ignore_permissions=True)
        doc.add_comment("Info", escape(f"{previous} → {target}."))
        order_notifications.status_changed(doc, previous)
        return serialize(doc)
    finally:
        _owner_operation.reset(owner_token)
        _order_operation.reset(token)


def update_driver_location(order, latitude, longitude, accuracy=None):
    doc = frappe.get_doc("LC Order", order)
    if doc.delivery_user != frappe.session.user or not is_shop_driver(
        frappe.session.user, doc.shop
    ):
        frappe.throw("This delivery is not assigned to you", frappe.PermissionError)
    # Keep the same shop-then-order lock order used by checkout and delivery changes.
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    frappe.db.sql("select name from `tabLC Order` where name=%s for update", doc.name)
    doc.reload()
    if doc.delivery_user != frappe.session.user or not is_shop_driver(
        frappe.session.user, doc.shop
    ):
        frappe.throw("This delivery is not assigned to you", frappe.PermissionError)
    if doc.status != "Out for Delivery":
        reject("Live location is available only while an order is out for delivery")
    shop = frappe.get_doc("LC Shop", doc.shop)
    if not shop.live_tracking_enabled:
        reject("Live delivery tracking is disabled for this shop")
    try:
        location = point(latitude, longitude, required=True)
    except ValueError as exc:
        reject(str(exc))
    try:
        location_accuracy = accuracy_metres(accuracy if accuracy is not None else 0)
    except ValueError as exc:
        reject(str(exc))
    now = now_datetime()
    if doc.driver_location_at and time_diff_in_seconds(now, doc.driver_location_at) < 10:
        return {"accepted": False, "updated_at": str(doc.driver_location_at)}
    token = _order_operation.set(True)
    try:
        doc.driver_latitude = location["latitude"]
        doc.driver_longitude = location["longitude"]
        doc.driver_location_accuracy = float(location_accuracy)
        doc.driver_location_at = now
        doc.save(ignore_permissions=True)
    finally:
        _order_operation.reset(token)
    payload = {
        "order": doc.name,
        **location,
        "accuracy": float(location_accuracy),
        "updated_at": str(now),
    }
    frappe.publish_realtime(
        "lc_delivery_location", payload, user=doc.customer_user, after_commit=True
    )
    return {"accepted": True, **payload}


def serialize_collection(doc):
    return {
        "name": doc.name,
        "order": doc.order,
        "shop": doc.shop,
        "shop_name": frappe.db.get_value("LC Shop", doc.shop, "shop_name"),
        "delivery_user": doc.delivery_user,
        "delivery_name": frappe.db.get_value("User", doc.delivery_user, "full_name")
        or doc.delivery_user,
        "currency": doc.currency,
        "expected_amount": doc.expected_amount,
        "collected_amount": doc.collected_amount,
        "variance": doc.variance,
        "status": doc.status,
        "collected_at": str(doc.collected_at),
        "driver_note": doc.driver_note,
        "reconciled_by": doc.reconciled_by,
        "reconciled_at": str(doc.reconciled_at) if doc.reconciled_at else None,
        "owner_note": doc.owner_note,
    }


def cod_collections(shop, view="pending", start=0):
    require_shop(shop)
    if view not in {"pending", "history"}:
        reject("Invalid cash collection view")
    status = "Awaiting Handover" if view == "pending" else "Reconciled"
    names = frappe.get_all(
        "LC COD Collection",
        filters={"shop": shop, "status": status},
        pluck="name",
        start=offset(start),
        limit_page_length=20,
        order_by="collected_at desc, name desc",
    )
    return [serialize_collection(frappe.get_doc("LC COD Collection", name)) for name in names]


def create_cod_payment(order, collected_amount):
    if not collected_amount:
        return None
    shop = frappe.get_doc("LC Shop", order.shop)
    validate_delivery(shop)
    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

        payment = get_payment_entry(
            "Sales Invoice",
            order.sales_invoice,
            bank_account=shop.cod_cash_account,
            reference_date=nowdate(),
        )
        amount = float(collected_amount)
        payment.paid_amount = amount
        payment.received_amount = amount
        remaining = amount
        for reference in payment.references:
            allocation = min(remaining, float(reference.outstanding_amount))
            reference.allocated_amount = allocation
            remaining -= allocation
        payment.mode_of_payment = shop.cod_mode_of_payment
        payment.lc_order = order.name
        payment.flags.ignore_permissions = True
        payment.insert(ignore_permissions=True)
        payment.submit()
        return payment.name
    finally:
        frappe.set_user(original_user)


def reconcile_cod(collection, owner_note=""):
    record = frappe.get_doc("LC COD Collection", collection)
    require_shop(record.shop, "write")
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", record.shop)
    frappe.db.sql("select name from `tabLC COD Collection` where name=%s for update", record.name)
    frappe.db.sql("select name from `tabLC Order` where name=%s for update", record.order)
    record.reload()
    if record.status == "Reconciled":
        return serialize_collection(record)
    owner_note = str(owner_note or "").strip()
    if record.variance and not 3 <= len(owner_note) <= 500:
        reject("Explain how the cash difference was reconciled (3–500 characters)")
    if len(owner_note) > 500:
        reject("Reconciliation note cannot exceed 500 characters")
    order = frappe.get_doc("LC Order", record.order)
    if order.status != "Delivered" or order.payment_status != "Collected":
        reject("This order is not ready for cash reconciliation")
    token = _order_operation.set(True)
    try:
        payment_entry = create_cod_payment(order, record.collected_amount)
        record.status = "Reconciled"
        record.reconciled_by = frappe.session.user
        record.reconciled_at = now_datetime()
        record.owner_note = owner_note
        record.save(ignore_permissions=True)
        order.payment_entry = payment_entry
        order.payment_status = "Reconciled"
        order.save(ignore_permissions=True)
        order.add_comment("Info", escape(f"Cash handover reconciled by {record.reconciled_by}."))
        return serialize_collection(record)
    finally:
        _order_operation.reset(token)


def change(order, target, reason=""):
    doc = frappe.get_doc("LC Order", order)
    is_customer = doc.customer_user == frappe.session.user and not can_access_shop(
        *identity(), memberships(frappe.session.user), doc.shop, "write"
    )
    if not is_customer:
        authorize(doc, True)
    # Match creation and inventory lock order, then refresh state after the lock.
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    frappe.db.sql("select name from `tabLC Order` where name=%s for update", doc.name)
    doc.reload()
    try:
        changed = order_rules.transition(doc.status, target, customer=is_customer)
    except ValueError as exc:
        reject(str(exc))
    if not changed:
        return serialize(doc)
    if target == "Ready" and any(
        line.get("option_id") and line.get("actual_weight") is None
        for line in json.loads(doc.get("selling_lines_json") or "[]")
    ):
        reject("Enter and save the actual packed weights before marking this order Ready")
    from local_commerce.services import fish

    if target in {"Accepted", "Ready"}:
        fish.validate_order(doc)
    if target == "Cancelled" and not 3 <= len(str(reason).strip()) <= 500:
        reject("Enter a cancellation reason (3–500 characters)")
    so = frappe.get_doc("Sales Order", doc.sales_order)
    token = _order_operation.set(True)
    owner_token = _owner_operation.set(True)
    try:
        so.flags.ignore_permissions = True
        if target == "Accepted":
            current_shop = public_shop(
                doc.shop, scheduled_delivery=doc.get("delivery_mode") == "Scheduled"
            )
            if so.company != current_shop.company:
                reject("Order Company no longer matches the shop")
            item_totals = {}
            for row in sorted(so.items, key=lambda r: r.item_code):
                item = frappe.get_doc("Item", row.item_code)
                if item.lc_shop != doc.shop or item.disabled or item.lc_sold_out:
                    reject("An order product is no longer available")
                company_link("Warehouse", row.warehouse, so.company, {"is_group": 0, "disabled": 0})
                stock = balance(row.item_code, row.warehouse, lock=True, exclude_order=doc.name)
                item_totals[row.item_code] = item_totals.get(row.item_code, 0) + row.stock_qty
                if item_totals[row.item_code] > stock["available"]:
                    reject("Not enough available stock to accept this order")
            so.submit()
        elif target == "Cancelled":
            if so.docstatus == 1:
                so.cancel()
            elif so.docstatus != 0:
                reject("This ERPNext order cannot be cancelled here")
        elif so.docstatus != 1:
            reject("The ERPNext order is not active; contact your administrator")
        previous = doc.status
        doc.status, doc.reason = target, str(reason).strip() if target == "Cancelled" else ""
        if target == "Cancelled":
            doc.fish_allocations_json = '[]'
        doc.save(ignore_permissions=True)
        doc.add_comment("Info", escape(f"{previous} → {target}. {doc.reason}"))
        order_notifications.status_changed(doc, previous)
        return serialize(doc)
    finally:
        _owner_operation.reset(owner_token)
        _order_operation.reset(token)


def expire_requested_orders():
    """Cancel unanswered requests; scheduler runs this once per minute."""
    names = frappe.db.sql_list(
        """
        select o.name
        from `tabLC Order` o
        inner join `tabLC Shop` s on s.name=o.shop
        left join `tabLC Delivery Slot` ds on ds.name=o.scheduled_slot
        where o.status='Requested'
          and timestampadd(
            minute,
            coalesce(nullif(s.order_response_minutes, 0), 10),
            coalesce(ds.ordering_end, o.creation)
          ) <= %s
        order by o.creation asc
        limit 200
        """,
        now_datetime(),
    )
    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        for name in names:
            try:
                change(name, "Cancelled", "Shop response timeout")
            except frappe.ValidationError:
                # An owner may have handled the order while this job waited for its lock.
                if frappe.db.get_value("LC Order", name, "status") == "Requested":
                    frappe.log_error(
                        title="Local Commerce order expiry failed",
                        message=f"Could not expire requested order {name}",
                    )
    finally:
        frappe.set_user(original_user)


def permission(doc, user=None, permission_type=None, **kwargs):
    user, roles = identity(user)
    if permission_type not in (None, "read"):
        return False
    return (
        (user != "Guest" and user == doc.customer_user)
        or (user == doc.delivery_user and is_shop_driver(user, doc.shop))
        or can_access_shop(user, roles, memberships(user), doc.shop)
    )


def collection_permission(doc, user=None, permission_type=None, **kwargs):
    user, roles = identity(user)
    if permission_type not in (None, "read"):
        return False
    return (user == doc.delivery_user and is_shop_driver(user, doc.shop)) or can_access_shop(
        user, roles, memberships(user), doc.shop
    )


def collection_query(user=None):
    user = user or frappe.session.user
    if user == "Guest":
        return "1=0"
    scoped = shop_query(user).replace("`tabLC Shop`.`name`", "`tabLC COD Collection`.`shop`")
    if not scoped:
        return ""
    return f"({scoped}) or `tabLC COD Collection`.`delivery_user`={frappe.db.escape(user)}"


def query(user=None):
    user = user or frappe.session.user
    if user == "Guest":
        return "1=0"
    scoped = shop_query(user).replace("`tabLC Shop`.`name`", "`tabLC Order`.`shop`")
    if not scoped:
        return ""
    return (
        f"({scoped}) or `tabLC Order`.`customer_user`={frappe.db.escape(user)}"
        f" or `tabLC Order`.`delivery_user`={frappe.db.escape(user)}"
    )


def protect_sales_order(doc, method=None, **kwargs):
    previous = doc.get_doc_before_save()
    if (
        doc.get("lc_order") or (previous and previous.get("lc_order"))
    ) and not _order_operation.get():
        frappe.throw("Use the Local Commerce order workflow", frappe.PermissionError)


def protect_delivery_note(doc, method=None, **kwargs):
    previous = doc.get_doc_before_save()
    if (
        doc.get("lc_order") or (previous and previous.get("lc_order"))
    ) and not _order_operation.get():
        frappe.throw("Use the Local Commerce delivery workflow", frappe.PermissionError)


def protect_payment_document(doc, method=None, **kwargs):
    previous = doc.get_doc_before_save()
    if (
        doc.get("lc_order") or (previous and previous.get("lc_order"))
    ) and not _order_operation.get():
        frappe.throw("Use the Local Commerce payment workflow", frappe.PermissionError)
