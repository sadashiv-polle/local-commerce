"""Delivery requests backed by ERPNext Sales Orders; no payment or delivery posting."""

import hashlib
import json
from contextvars import ContextVar
from html import escape

import frappe
from frappe.utils import getdate, nowdate

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


def validate_delivery(doc, method=None):
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


def public_shop(name):
    doc = frappe.get_doc("LC Shop", name)
    if doc.status != "Active" or not doc.delivery_enabled:
        reject("This shop is not accepting delivery requests")
    validate_delivery(doc)
    return doc


def shops(start=0):
    return frappe.get_all(
        "LC Shop",
        filters={"status": "Active", "delivery_enabled": 1},
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
        reject("A product has no current selling price")
    currency = frappe.db.get_value("Company", shop.company, "default_currency")
    if price.currency != currency:
        reject("Product currency does not match this shop")
    return {
        "item": item.name,
        "item_name": item.item_name,
        "uom": item.stock_uom,
        "description": item.lc_description or "",
        "rate": float(checked_number(price.price_list_rate, "Price")),
        "currency": currency,
        "available": 0 if item.lc_sold_out else balance(item.name, shop.warehouse)["available"],
    }


def catalog(shop, start=0):
    doc = public_shop(shop)
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
        price = get_price(doc, item)
        if not price or item.variant_of:
            continue
        if (price.valid_from and getdate(price.valid_from) > getdate(nowdate())) or (
            price.valid_upto and getdate(price.valid_upto) < getdate(nowdate())
        ):
            continue
        products.append(product_data(doc, item, browsing=True))
    return {
        "shop_name": doc.shop_name,
        "items": products,
        "has_more": len(names) == 20,
        "delivery_fee": doc.delivery_fee or 0,
        "postal_codes": doc.delivery_postcodes,
        "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
    }


def customer_record(user, company):
    from local_commerce.services.customers import ensure_customer

    if user != frappe.session.user:
        frappe.throw("Customer access denied", frappe.PermissionError)
    return ensure_customer()["name"]


def place(shop, items, address, request_key):
    user = customer_access()
    try:
        rows = order_rules.cart_rows(frappe.parse_json(items))
        address = order_rules.address_fields(frappe.parse_json(address))
    except (ValueError, TypeError) as exc:
        reject(str(exc))
    if not isinstance(request_key, str) or not 16 <= len(request_key) <= 100:
        reject("Invalid request key")
    key = hashlib.sha256(f"{user}:{shop}:{request_key}".encode()).hexdigest()
    digest = hashlib.sha256(json.dumps([rows, address], sort_keys=True).encode()).hexdigest()
    # Same lock order as owner stock operations. One shop's checkout is serialized.
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", shop)
    previous = frappe.db.get_value(
        "LC Order", {"request_key": key}, ["name", "request_hash"], as_dict=True
    )
    if previous:
        if previous.request_hash != digest:
            reject("This request key was already used for another order")
        return detail(previous.name)
    doc = public_shop(shop)
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
                "links": [{"link_doctype": "Customer", "link_name": customer}],
            }
        ).insert(ignore_permissions=True)
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
    return (user != "Guest" and user == doc.customer_user) or can_access_shop(
        user, roles, memberships(user), doc.shop
    )


def query(user=None):
    user = user or frappe.session.user
    if user == "Guest":
        return "1=0"
    scoped = shop_query(user).replace("`tabLC Shop`.`name`", "`tabLC Order`.`shop`")
    if not scoped:
        return ""
    return f"({scoped}) or `tabLC Order`.`customer_user`={frappe.db.escape(user)}"


def protect_sales_order(doc, method=None, **kwargs):
    previous = doc.get_doc_before_save()
    if (
        doc.get("lc_order") or (previous and previous.get("lc_order"))
    ) and not _order_operation.get():
        frappe.throw("Use the Local Commerce order workflow", frappe.PermissionError)
