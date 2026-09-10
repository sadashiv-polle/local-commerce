"""Delivery orders backed by ERPNext Sales Orders and Delivery Notes; no online payment."""

import hashlib
import json
from contextvars import ContextVar
from html import escape

import frappe
from frappe.utils import getdate, now_datetime, nowdate

from local_commerce.permissions.policy import can_access_shop
from local_commerce.permissions.scope import identity, memberships, require_shop, shop_query
from local_commerce.services import order_rules
from local_commerce.services.owner import (
    _owner_operation,
    balance,
    checked_number,
    company_link,
    get_price,
    reject,
)

_order_operation = ContextVar("lc_order_operation", default=False)


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
                {"shop": shop, "user": user, "membership_role": "Driver", "enabled": 1},
            )
        )
    )


def validate_delivery(doc, method=None):
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
    if not doc.delivery_enabled:
        return
    if not doc.delivery_postcodes or not doc.warehouse or not doc.selling_price_list:
        reject(
            "Set warehouse, selling price list and delivery postal codes before enabling delivery"
        )
    company_link("Warehouse", doc.warehouse, doc.company, {"is_group": 0, "disabled": 0})
    if not frappe.db.exists(
        "Sales Taxes and Charges Template",
        {
            "name": doc.order_tax_template,
            "company": doc.company,
            "disabled": 0,
        },
    ):
        reject("Select an order tax template belonging to the shop Company")
    fee = checked_number(doc.delivery_fee or 0, "Delivery fee")
    if fee:
        company_link("Account", doc.delivery_account, doc.company, {"is_group": 0, "disabled": 0})


def public_shop(name, browsing=False):
    doc = frappe.get_doc("LC Shop", name)
    if doc.status != "Active" or (not browsing and not doc.delivery_enabled):
        reject("This shop is not accepting delivery requests")
    if not browsing:
        validate_delivery(doc)
    return doc


def shops(start=0):
    return frappe.get_all(
        "LC Shop",
        filters={"status": "Active"},
        fields=["name", "shop_name", "description"],
        start=offset(start),
        limit_page_length=20,
    )


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
    return {
        "item": item.name,
        "item_name": item.item_name,
        "uom": item.stock_uom,
        "description": item.lc_description or "",
        "rate": float(checked_number(price.price_list_rate, "Price")) if price else None,
        "currency": currency,
        "available": 0 if item.lc_sold_out else balance(item.name, shop.warehouse)["available"],
    }


def catalog(shop, start=0):
    doc = public_shop(shop, browsing=True)
    names = frappe.get_all(
        "Item",
        filters={
            "lc_shop": shop,
            "disabled": 0,
            "is_stock_item": 1,
            "has_batch_no": 0,
            "has_serial_no": 0,
            "has_variants": 0,
        },
        pluck="name",
        start=offset(start),
        limit_page_length=20,
        order_by="item_name asc",
    )
    products = []
    for name in names:
        item = frappe.get_doc("Item", name)
        if item.variant_of:
            continue
        products.append(product_data(doc, item, browsing=True))
    return {
        "shop_name": doc.shop_name,
        "accepting_orders": bool(doc.delivery_enabled and doc.cod_enabled),
        "items": products,
        "has_more": len(names) == 20,
        "delivery_fee": doc.delivery_fee or 0,
        "postal_codes": doc.delivery_postcodes,
        "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
        "payment_methods": ["Cash on Delivery"] if doc.cod_enabled else [],
        "payment_message": (
            "Pay the rider when your order arrives"
            if doc.cod_enabled
            else "This shop is setting up customer payments"
        ),
    }


def customer_record(user, company):
    from local_commerce.services.customers import ensure_customer

    if user != frappe.session.user:
        frappe.throw("Customer access denied", frappe.PermissionError)
    return ensure_customer()["name"]


def place(shop, items, address, request_key, payment_method="Cash on Delivery"):
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
        json.dumps([rows, address, payment_method], sort_keys=True).encode()
    ).hexdigest()
    legacy_digest = hashlib.sha256(json.dumps([rows, address], sort_keys=True).encode()).hexdigest()
    # Same lock order as owner stock operations. One shop's checkout is serialized.
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", shop)
    previous = frappe.db.get_value(
        "LC Order", {"request_key": key}, ["name", "request_hash"], as_dict=True
    )
    if previous:
        if previous.request_hash not in {digest, legacy_digest}:
            reject("This request key was already used for another order")
        return detail(previous.name)
    doc = public_shop(shop)
    if not doc.cod_enabled:
        reject("Cash on Delivery is not configured for this shop")
    allowed = {p.strip().upper() for p in doc.delivery_postcodes.splitlines() if p.strip()}
    if address["postal_code"] not in allowed:
        reject("This shop does not deliver to that postal code")
    prepared = []
    for row in rows:
        item = frappe.get_doc("Item", row["item"])
        product = product_data(doc, item)
        quantity = checked_number(row["quantity"], "Quantity", positive=True)
        try:
            order_rules.whole_quantity(
                quantity, frappe.db.get_value("UOM", item.stock_uom, "must_be_whole_number")
            )
        except ValueError as exc:
            reject(str(exc))
        if quantity > checked_number(
            balance(item.name, doc.warehouse, lock=True)["available"], "Available stock"
        ):
            reject("Not enough available stock; update your cart")
        prepared.append(
            {
                "item_code": item.name,
                "item_name": item.item_name,
                "qty": float(quantity),
                "rate": product["rate"],
                "price_list_rate": product["rate"],
                "uom": item.stock_uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": 1,
                "warehouse": doc.warehouse,
                "delivery_date": nowdate(),
            }
        )
    token = _order_operation.set(True)
    owner_token = _owner_operation.set(True)
    try:
        order = frappe.get_doc(
            {
                "doctype": "LC Order",
                "request_key": key,
                "request_hash": digest,
                "shop": shop,
                "customer_user": user,
                "status": "Requested",
                "payment_method": payment_method,
                "payment_status": "Pending",
                "recipient": address["recipient"],
                "phone": address["phone"],
                "address_snapshot": json.dumps(address),
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
                "delivery_date": nowdate(),
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

        so.set(
            "taxes",
            get_taxes_and_charges("Sales Taxes and Charges Template", doc.order_tax_template),
        )
        so.flags.ignore_permissions = True
        so.set_missing_values()
        if doc.delivery_fee:
            so.append(
                "taxes",
                {
                    "charge_type": "Actual",
                    "account_head": doc.delivery_account,
                    "description": "Delivery charge",
                    "tax_amount": doc.delivery_fee,
                },
            )
        so.insert(ignore_permissions=True)
        for expected, posted in zip(prepared, so.items, strict=True):
            if checked_number(posted.qty, "Quantity") != checked_number(
                expected["qty"], "Quantity"
            ):
                reject("ERPNext quantity precision changed this order; use a supported quantity")
        order.sales_order = so.name
        order.save(ignore_permissions=True)
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
    return {
        "name": doc.name,
        "shop": doc.shop,
        "shop_name": frappe.db.get_value("LC Shop", doc.shop, "shop_name"),
        "status": doc.status,
        "created": str(doc.creation),
        "recipient": doc.recipient,
        "phone": doc.phone,
        "address": json.loads(doc.address_snapshot),
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


def list_orders(shop=None, start=0):
    if shop:
        require_shop(shop)
        filters = {"shop": shop}
    else:
        customer_access()
        filters = {"customer_user": frappe.session.user}
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
        filters={"shop": shop, "membership_role": "Driver", "enabled": 1},
        pluck="user",
        order_by="user asc",
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
        return serialize(doc)
    finally:
        _order_operation.reset(token)


def driver_shops(user=None):
    user = user or frappe.session.user
    if user == "Guest" or "LC Delivery Person" not in frappe.get_roles(user):
        frappe.throw("Delivery person access required", frappe.PermissionError)
    return sorted(
        {
            member.shop
            for member in memberships(user)
            if member.membership_role == "Driver" and is_shop_driver(user, member.shop)
        }
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


def delivery_change(order, target, collected_amount=None, note=""):
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
                delivery_note.submit()
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
            invoice, collection = create_cod_collection(doc, collected_amount, note)
            doc.sales_invoice = invoice
            doc.payment_status = "Collected"
            doc.collected_at = now_datetime()
            doc.delivered_at = now_datetime()
        previous = doc.status
        doc.status = target
        doc.save(ignore_permissions=True)
        doc.add_comment("Info", escape(f"{previous} → {target}."))
        return serialize(doc)
    finally:
        _owner_operation.reset(owner_token)
        _order_operation.reset(token)


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
    if target == "Cancelled" and not 3 <= len(str(reason).strip()) <= 500:
        reject("Enter a cancellation reason (3–500 characters)")
    so = frappe.get_doc("Sales Order", doc.sales_order)
    token = _order_operation.set(True)
    owner_token = _owner_operation.set(True)
    try:
        so.flags.ignore_permissions = True
        if target == "Accepted":
            current_shop = public_shop(doc.shop)
            if so.company != current_shop.company:
                reject("Order Company no longer matches the shop")
            for row in sorted(so.items, key=lambda r: r.item_code):
                item = frappe.get_doc("Item", row.item_code)
                if item.lc_shop != doc.shop or item.disabled or item.lc_sold_out:
                    reject("An order product is no longer available")
                company_link("Warehouse", row.warehouse, so.company, {"is_group": 0, "disabled": 0})
                stock = balance(row.item_code, row.warehouse, lock=True)
                if row.stock_qty > stock["available"]:
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
        doc.save(ignore_permissions=True)
        doc.add_comment("Info", escape(f"{previous} → {target}. {doc.reason}"))
        return serialize(doc)
    finally:
        _owner_operation.reset(owner_token)
        _order_operation.reset(token)


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
