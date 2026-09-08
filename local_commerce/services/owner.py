"""Owner catalog and inventory operations. No direct writes to Bin or ledgers."""

import hashlib
import json
from contextvars import ContextVar
from html import escape

import frappe

from local_commerce.permissions.scope import require_shop
from local_commerce.services.owner_rules import availability, number, stock_change
from local_commerce.services.products import _item_creation, tenant_user

_owner_operation = ContextVar("lc_owner_operation", default=False)


def reject(message):
    # Explicit safe error contract; frontend does not display arbitrary ERPNext traces.
    frappe.local.response["lc_message"] = message
    frappe.throw(message)


def checked_number(value, label, **kwargs):
    try:
        return number(value, label, **kwargs)
    except ValueError as exc:
        reject(str(exc))


def shop_doc(shop, write=False):
    require_shop(shop, "write" if write else "read")
    if write:
        frappe.db.sql("select name from `tabLC Shop` where name=%s for update", (shop,))
    return frappe.get_doc("LC Shop", shop)


def own_item(shop, item, write=False):
    shop_record = shop_doc(shop, write)
    if frappe.db.get_value("Item", item, "lc_shop") != shop:
        frappe.throw("Product access denied", frappe.PermissionError)
    if write:
        frappe.db.sql("select name from `tabItem` where name=%s for update", (item,))
    return shop_record, frappe.get_doc("Item", item)


def company_link(doctype, name, company, extra=None):
    if not name or not frappe.db.exists(
        doctype, {"name": name, "company": company, **(extra or {})}
    ):
        reject(f"Select a valid {doctype} belonging to this shop Company")


def validate_configuration(doc, method=None):
    previous = doc.get_doc_before_save()
    if (
        previous
        and previous.company != doc.company
        and frappe.db.exists("Item", {"lc_shop": doc.name})
    ):
        reject("Company cannot change after shop products have been created")
    for dt, field, extra in [
        ("Warehouse", "warehouse", {"is_group": 0, "disabled": 0}),
        (
            "Account",
            "stock_adjustment_account",
            {"is_group": 0, "disabled": 0, "account_type": "Stock Adjustment"},
        ),
        ("Cost Center", "cost_center", {"is_group": 0, "disabled": 0}),
    ]:
        if doc.get(field):
            company_link(dt, doc.get(field), doc.company, extra)
    if doc.selling_price_list:
        currency = frappe.db.get_value("Company", doc.company, "default_currency")
        if not frappe.db.exists(
            "Price List",
            {"name": doc.selling_price_list, "selling": 1, "enabled": 1, "currency": currency},
        ):
            reject("Shop price list must be enabled, selling, and use the Company currency")
    if (
        previous
        and previous.selling_price_list != doc.selling_price_list
        and not _owner_operation.get()
    ):
        reject("Use inventory setup to configure the selling price list")
    if doc.is_new() and doc.selling_price_list:
        reject("Save the shop first, then use inventory setup")


def setup_options(shop):
    doc = shop_doc(shop, True)
    return {
        "warehouse": doc.warehouse,
        "account": doc.stock_adjustment_account,
        "cost_center": doc.cost_center,
        "price_list": doc.selling_price_list,
        "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
        "warehouses": frappe.get_all(
            "Warehouse",
            filters={"company": doc.company, "is_group": 0, "disabled": 0},
            pluck="name",
            limit_page_length=500,
        ),
        "accounts": frappe.get_all(
            "Account",
            filters={
                "company": doc.company,
                "is_group": 0,
                "disabled": 0,
                "account_type": "Stock Adjustment",
            },
            pluck="name",
            limit_page_length=500,
        ),
        "cost_centers": frappe.get_all(
            "Cost Center",
            filters={"company": doc.company, "is_group": 0, "disabled": 0},
            pluck="name",
            limit_page_length=500,
        ),
    }


def configure(shop, warehouse, account, cost_center):
    doc = shop_doc(shop, True)
    doc.warehouse, doc.stock_adjustment_account, doc.cost_center = warehouse, account, cost_center
    validate_configuration(doc)
    token = _owner_operation.set(True)
    try:
        if not doc.selling_price_list:
            price_list = frappe.get_doc(
                {
                    "doctype": "Price List",
                    "price_list_name": "LC-" + frappe.generate_hash(length=20),
                    "selling": 1,
                    "buying": 0,
                    "enabled": 1,
                    "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
                }
            )
            price_list.insert(ignore_permissions=True)
            doc.selling_price_list = price_list.name
        doc.save()
    finally:
        _owner_operation.reset(token)
    return setup_options(shop)


def balance(item, warehouse, lock=False):
    if not warehouse:
        return {"actual": 0, "reserved": 0, "available": 0}
    fields = [
        "actual_qty",
        "reserved_qty",
        "reserved_qty_for_production",
        "reserved_qty_for_sub_contract",
        "reserved_qty_for_production_plan",
        "reserved_stock",
    ]
    fields = [field for field in fields if frappe.get_meta("Bin").has_field(field)]
    row = (
        frappe.db.get_value(
            "Bin", {"item_code": item, "warehouse": warehouse}, fields, as_dict=True
        )
        or {}
    )
    if lock:
        rows = frappe.db.sql(
            "select "
            + ",".join(fields)
            + " from `tabBin` where item_code=%s and warehouse=%s for update",
            (item, warehouse),
            as_dict=True,
        )
        row = rows[0] if rows else {}
    return stock_summary(row, fields)


def stock_summary(row, fields):
    actual = float(row.get("actual_qty") or 0)
    # Conservative: explicit reservations can overlap Sales Order reservations.
    # Never advertise more than the amount left by either representation.
    commitments = sum(
        float(row.get(f) or 0) for f in fields if f not in ("actual_qty", "reserved_stock")
    )
    reserved = max(commitments, float(row.get("reserved_stock") or 0))
    return {"actual": actual, "reserved": reserved, "available": max(0, actual - reserved)}


def get_price(shop, item):
    if not shop.selling_price_list:
        return None
    rows = frappe.db.sql(
        """
        select name, price_list_rate, currency, valid_from, valid_upto from `tabItem Price`
        where item_code=%s and price_list=%s and uom=%s
          and coalesce(customer, '')='' and coalesce(supplier, '')=''
          and coalesce(batch_no, '')='' limit 2
    """,
        (item.name, shop.selling_price_list, item.stock_uom),
        as_dict=True,
    )
    if len(rows) > 1:
        reject(
            "Multiple selling prices exist for this product; ask your administrator to resolve them"
        )
    return rows[0] if rows else None


def detail(shop, item):
    doc, product = own_item(shop, item)
    stock = balance(item, doc.warehouse)
    price = get_price(doc, product)
    currency = frappe.db.get_value("Company", doc.company, "default_currency")
    return serialize_product(doc, product, stock, price, currency)


def serialize_product(doc, product, stock, price, currency):
    return {
        **{
            key: product.get(key)
            for key in (
                "name",
                "item_name",
                "item_group",
                "stock_uom",
                "lc_description",
                "lc_sold_out",
                "lc_low_stock",
                "disabled",
                "modified",
            )
        },
        "stock": stock,
        "warehouse": doc.warehouse,
        "price": price.price_list_rate if price else None,
        "currency": currency,
        "availability": availability(stock["available"], product.lc_sold_out, product.disabled),
    }


def catalog(shop, start=0, search="", status="All"):
    doc = shop_doc(shop)
    start = int(start)
    if start < 0 or not isinstance(search, str) or len(search) > 140:
        reject("Invalid search or page")
    filters = {"lc_shop": shop}
    if status == "Archived":
        filters["disabled"] = 1
    elif status == "Active":
        filters["disabled"] = 0
    elif status == "Sold out":
        filters.update(disabled=0, lc_sold_out=1)
    elif status != "All":
        reject("Invalid product filter")
    if search.strip():
        filters["item_name"] = ["like", "%" + search.strip() + "%"]
    items = frappe.get_all(
        "Item",
        filters=filters,
        fields=[
            "name",
            "item_name",
            "item_group",
            "stock_uom",
            "lc_description",
            "lc_sold_out",
            "lc_low_stock",
            "disabled",
            "modified",
        ],
        start=start,
        limit_page_length=20,
        order_by="modified desc, name desc",
    )
    names = [item.name for item in items]
    stock_fields = [
        f
        for f in (
            "actual_qty",
            "reserved_qty",
            "reserved_qty_for_production",
            "reserved_qty_for_sub_contract",
            "reserved_qty_for_production_plan",
            "reserved_stock",
        )
        if frappe.get_meta("Bin").has_field(f)
    ]
    bins = (
        {
            row.item_code: row
            for row in frappe.get_all(
                "Bin",
                filters={"item_code": ["in", names], "warehouse": doc.warehouse},
                fields=["item_code", *stock_fields],
                limit_page_length=20,
            )
        }
        if names and doc.warehouse
        else {}
    )
    prices = {}
    if names and doc.selling_price_list:
        price_rows = frappe.db.sql(
            """
            select p.item_code, p.price_list_rate from `tabItem Price` p
            inner join `tabItem` i on i.name=p.item_code and i.stock_uom=p.uom
            where p.price_list=%s and p.item_code in ({placeholders})
            and coalesce(p.customer, '')='' and coalesce(p.supplier, '')=''
            and coalesce(p.batch_no, '')='' limit 41
        """.format(placeholders=",".join(["%s"] * len(names))),
            (doc.selling_price_list, *names),
            as_dict=True,
        )
        for row in price_rows:
            if row.item_code in prices:
                reject("Multiple selling prices exist; ask your administrator to resolve them")
            prices[row.item_code] = row
    currency = frappe.db.get_value("Company", doc.company, "default_currency")
    return {
        "items": [
            serialize_product(
                doc,
                item,
                stock_summary(bins.get(item.name, {}), stock_fields),
                prices.get(item.name),
                currency,
            )
            for item in items
        ],
        "total": frappe.db.count("Item", filters),
        "warehouse": doc.warehouse,
        "configured": bool(doc.warehouse and doc.selling_price_list),
        "summary": {
            "products": frappe.db.count("Item", {"lc_shop": shop}),
            "archived": frappe.db.count("Item", {"lc_shop": shop, "disabled": 1}),
            "paused": frappe.db.count("Item", {"lc_shop": shop, "lc_sold_out": 1, "disabled": 0}),
        },
    }


def update_product(
    shop, item, modified, item_name, description="", low_stock=0, sold_out=0, archived=0, price=None
):
    doc, product = own_item(shop, item, True)
    if str(product.modified) != str(modified):
        reject("This product changed. Refresh it before saving again")
    if not isinstance(item_name, str) or not 1 <= len(item_name.strip()) <= 140:
        reject("Product name must contain 1 to 140 characters")
    if not isinstance(description, str) or len(description) > 5000:
        reject("Description must be at most 5000 characters")
    if str(sold_out) not in ("0", "1") or str(archived) not in ("0", "1"):
        reject("Invalid availability setting")
    product.item_name = item_name.strip()
    product.lc_description = description
    product.description = escape(description) if description else escape(product.item_name)
    product.lc_low_stock = float(checked_number(low_stock, "Low-stock threshold"))
    product.lc_sold_out, product.disabled = int(sold_out), int(archived)
    if price not in (None, ""):
        rate = checked_number(price, "Selling price")
        if not doc.selling_price_list:
            reject("Complete inventory and pricing setup first")
        price_doc = get_price(doc, product)
        if price_doc and (
            price_doc.valid_upto or str(price_doc.valid_from or "") > frappe.utils.today()
        ):
            reject("This price has scheduled validity; manage it through ERPNext first")
        if price_doc:
            price_record = frappe.get_doc("Item Price", price_doc.name)
        else:
            price_record = frappe.get_doc(
                {
                    "doctype": "Item Price",
                    "item_code": product.name,
                    "price_list": doc.selling_price_list,
                    "uom": product.stock_uom,
                    "customer": "",
                    "supplier": "",
                    "batch_no": "",
                }
            )
        old_rate = price_record.price_list_rate
        price_record.price_list_rate = float(rate)
        token = _owner_operation.set(True)
        try:
            price_record.save(ignore_permissions=True)
            price_record.add_comment("Edit", f"Owner selling-price change: {old_rate} to {rate}")
        finally:
            _owner_operation.reset(token)
    token = _item_creation.set(True)
    try:
        product.save(ignore_permissions=True)
        product.add_comment("Edit", "Owner updated product details, availability or selling price")
    finally:
        _item_creation.reset(token)
    return detail(shop, item)


def adjust_stock(shop, item, action, quantity, reason, request_key, unit_cost=0):
    doc, product = own_item(shop, item, True)
    if not isinstance(request_key, str) or not 16 <= len(request_key) <= 100:
        reject("A valid request key is required")
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
        reject("Enter a stock adjustment reason of 3 to 500 characters")
    if product.has_batch_no or product.has_serial_no or product.has_variants:
        reject("Batch, serial and template items require the ERPNext stock workflow")
    if not product.is_stock_item:
        reject("This item does not maintain stock")
    if not doc.warehouse or not doc.stock_adjustment_account or not doc.cost_center:
        reject("Complete warehouse and adjustment-account setup first")
    validate_configuration(doc)
    request_id = hashlib.sha256(f"{frappe.session.user}:{shop}:{request_key}".encode()).hexdigest()
    payload = {
        "item": item,
        "action": action,
        "quantity": str(quantity),
        "unit_cost": str(unit_cost),
        "reason": reason.strip(),
    }
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    previous = frappe.db.get_value(
        "LC Stock Operation", request_id, ["payload_hash", "stock_entry"], as_dict=True
    )
    if previous:
        if previous.payload_hash != payload_hash:
            reject("This request key was already used for a different adjustment")
        return {"stock_entry": previous.stock_entry, "replayed": True}
    if product.disabled:
        reject("Restore the archived product before adjusting its stock")
    stock = balance(item, doc.warehouse, lock=True)
    try:
        qty, cost = stock_change(
            action,
            quantity,
            unit_cost,
            stock["actual"],
            stock["reserved"],
            bool(frappe.db.get_value("UOM", product.stock_uom, "must_be_whole_number")),
        )
    except ValueError as exc:
        reject(str(exc))
    row = {
        "item_code": item,
        "qty": float(qty),
        "uom": product.stock_uom,
        "stock_uom": product.stock_uom,
        "conversion_factor": 1,
        "expense_account": doc.stock_adjustment_account,
        "cost_center": doc.cost_center,
    }
    if action == "Add":
        row.update(t_warehouse=doc.warehouse, basic_rate=float(cost), set_basic_rate_manually=1)
    else:
        row.update(s_warehouse=doc.warehouse)
    token = _owner_operation.set(True)
    try:
        operation = frappe.get_doc(
            {
                "doctype": "LC Stock Operation",
                "request_id": request_id,
                "payload_hash": payload_hash,
                "shop": shop,
                "company": doc.company,
                "item": item,
                "warehouse": doc.warehouse,
                "action": action,
                "quantity": float(qty),
                "unit_cost": float(cost),
                "reason": reason.strip(),
                "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
            }
        )
        operation.insert(ignore_permissions=True)
        entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt" if action == "Add" else "Material Issue",
                "purpose": "Material Receipt" if action == "Add" else "Material Issue",
                "company": doc.company,
                "lc_shop": shop,
                "remarks": reason.strip(),
                "items": [row],
            }
        )
        entry.flags.ignore_permissions = True
        entry.insert(ignore_permissions=True)
        if checked_number(entry.items[0].qty, "Posted quantity") != qty:
            reject("Quantity has more decimal places than the ERPNext stock precision allows")
        entry.submit()
        operation.quantity = entry.items[0].qty
        operation.unit_cost = entry.items[0].basic_rate
        operation.stock_entry = entry.name
        operation.save(ignore_permissions=True)
    finally:
        _owner_operation.reset(token)
    return {"stock_entry": entry.name, "replayed": False}


def history(shop, item, start=0):
    own_item(shop, item)
    start = int(start)
    if start < 0:
        reject("Invalid page")
    return frappe.get_all(
        "LC Stock Operation",
        filters={"shop": shop, "item": item},
        fields=[
            "name",
            "creation",
            "owner",
            "action",
            "quantity",
            "warehouse",
            "reason",
            "stock_entry",
        ],
        order_by="creation desc, name desc",
        start=start,
        limit_page_length=20,
    )


def operation_permission(doc, user=None, permission_type=None, **kwargs):
    from local_commerce.permissions.policy import can_access_shop
    from local_commerce.permissions.scope import identity, memberships

    user, roles = identity(user)
    return permission_type in (None, "read") and can_access_shop(
        user, roles, memberships(user), doc.shop
    )


def operation_query(user=None):
    from local_commerce.permissions.scope import shop_query

    return shop_query(user).replace("`tabLC Shop`.`name`", "`tabLC Stock Operation`.`shop`")


def restricted_permission(doc, user=None, permission_type=None, **kwargs):
    return False if tenant_user(user)[2] else None


def restricted_query(user=None):
    return "1=0" if tenant_user(user)[2] else ""


def restricted_write(doc, method=None, *args, **kwargs):
    if tenant_user()[2] and not _owner_operation.get():
        frappe.throw("Use the Local Commerce owner workspace", frappe.PermissionError)


def immutable_stock_entry(doc, method=None):
    if doc.get("lc_shop") and not _owner_operation.get():
        frappe.throw(
            "Use an opposite stock adjustment to correct this entry", frappe.PermissionError
        )
