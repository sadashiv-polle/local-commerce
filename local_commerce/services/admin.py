"""Platform-only operational dashboard. Financial totals stay separated by currency."""

from datetime import timedelta

import frappe
from frappe.utils import getdate, nowdate

from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import balance, reject


def overview():
    require_platform()
    today = getdate(nowdate())
    until = today + timedelta(days=1)
    since = today - timedelta(days=6)
    statuses = frappe.get_all("LC Order", fields=["status", "count(name) as count"],
                              group_by="status", limit_page_length=0)
    counts = {row.status: row.count for row in statuses}
    sales = frappe.db.sql(
        """select so.currency, count(*) as orders, sum(so.grand_total) as amount
        from `tabLC Order` o inner join `tabSales Order` so on so.name=o.sales_order
        where o.status='Delivered' and o.delivered_at >= %s and o.delivered_at < %s
        group by so.currency""", (today, until), as_dict=True,
    )
    cash = frappe.db.sql(
        """select currency, count(*) as collections, sum(collected_amount) as amount
        from `tabLC COD Collection` where status='Awaiting Handover'
        group by currency""", as_dict=True,
    )
    trend = frappe.db.sql(
        """select date(o.delivered_at) as day, so.currency,
        count(*) as orders, sum(so.grand_total) as amount
        from `tabLC Order` o inner join `tabSales Order` so on so.name=o.sales_order
        where o.status='Delivered' and o.delivered_at >= %s and o.delivered_at < %s
        group by date(o.delivered_at), so.currency order by day""",
        (since, until), as_dict=True,
    )
    shops = frappe.get_all(
        "LC Shop", fields=["name", "shop_name", "company", "status"],
        order_by="shop_name asc, name asc", limit_page_length=500,
    )
    setup = frappe.db.count("LC Shop", {"status": "Active", "warehouse": ["is", "not set"]})
    return {
        "date": str(today), "updated_at": frappe.utils.now_datetime(),
        "shops": frappe.db.count("LC Shop"),
        "active_shops": frappe.db.count("LC Shop", {"status": "Active"}),
        "customers": frappe.db.count("LC Customer Account"),
        "riders": frappe.db.sql(
            """select count(distinct m.user) from `tabLC Shop Member` m
            inner join `tabUser` u on u.name=m.user
            where m.enabled=1 and m.membership_role='Driver' and u.enabled=1"""
        )[0][0],
        "products": frappe.db.count("Item", {"lc_shop": ["is", "set"], "disabled": 0}),
        "new_orders_today": frappe.db.sql(
            "select count(*) from `tabLC Order` where creation >= %s and creation < %s",
            (today, until),
        )[0][0],
        "pending_orders": counts.get("Requested", 0),
        "active_orders": sum(count for status, count in counts.items()
                             if status not in {"Delivered", "Cancelled"}),
        "out_for_delivery": counts.get("Out for Delivery", 0),
        "statuses": counts, "sales_today": sales, "cash_pending": cash,
        "trend": trend, "shop_options": shops, "inventory_setup_pending": setup,
    }


def listing(section, search="", shop="", status="", start=0):
    require_platform()
    try:
        start = int(start)
    except (TypeError, ValueError):
        reject("Invalid page")
    if start < 0 or start > 100000:
        reject("Invalid page")
    search, shop, status = str(search or "").strip()[:140], str(shop or ""), str(status or "")
    specs = {
        "shops": (
            "s.name, s.shop_name, s.company, s.status, s.city, s.accepting_orders, "
            "s.delivery_enabled, s.warehouse",
            "`tabLC Shop` s", "s.name", "s.shop_name", "s.status",
            ["s.shop_name", "s.company", "s.city"],
        ),
        "orders": (
            "o.name, o.shop, s.shop_name, o.recipient, o.status, o.delivery_user, "
            "o.creation, o.payment_status, so.currency, so.grand_total as amount",
            "`tabLC Order` o inner join `tabLC Shop` s on s.name=o.shop "
            "left join `tabSales Order` so on so.name=o.sales_order",
            "o.shop", "o.creation desc", "o.status",
            ["o.name", "o.recipient", "s.shop_name", "o.delivery_user"],
        ),
        "people": (
            "m.name, m.shop, s.shop_name, m.user, u.full_name, u.user_image, "
            "m.membership_role, m.enabled, u.enabled as account_enabled, u.mobile_no",
            "`tabLC Shop Member` m inner join `tabLC Shop` s on s.name=m.shop "
            "inner join `tabUser` u on u.name=m.user",
            "m.shop", "u.full_name", "m.membership_role",
            ["u.full_name", "m.user", "s.shop_name"],
        ),
        "customers": (
            "a.name, a.customer, u.full_name, u.email, u.mobile_no, u.enabled",
            "`tabLC Customer Account` a inner join `tabUser` u on u.name=a.name",
            None, "u.full_name", None, ["u.full_name", "u.email", "a.customer"],
        ),
        "inventory": (
            "i.name, i.item_name, i.item_group, i.stock_uom, i.image, i.disabled, "
            "i.lc_shop as shop, i.lc_sold_out, i.lc_low_stock, s.shop_name, s.warehouse",
            "`tabItem` i inner join `tabLC Shop` s on s.name=i.lc_shop",
            "i.lc_shop", "i.item_name", None, ["i.item_name", "i.item_group", "s.shop_name"],
        ),
        "payments": (
            "c.name, c.order, c.shop, s.shop_name, c.delivery_user, c.currency, "
            "c.collected_amount, c.expected_amount, c.variance, c.status, c.collected_at",
            "`tabLC COD Collection` c inner join `tabLC Shop` s on s.name=c.shop",
            "c.shop", "c.collected_at desc", "c.status",
            ["s.shop_name", "c.delivery_user", "c.order"],
        ),
    }
    if section not in specs:
        reject("Choose a dashboard section")
    fields, source, shop_field, ordering, status_field, searchable = specs[section]
    conditions, values = [], []
    if shop and shop_field:
        conditions.append(f"{shop_field}=%s")
        values.append(shop)
    if status and status_field:
        conditions.append(f"{status_field}=%s")
        values.append(status)
    if search:
        conditions.append("(" + " or ".join(f"{field} like %s" for field in searchable) + ")")
        values.extend([f"%{search}%"] * len(searchable))
    where = " where " + " and ".join(conditions) if conditions else ""
    # All interpolated SQL fragments above are fixed server-side identifiers.
    rows = frappe.db.sql(f"select {fields} from {source}{where} "
                         f"order by {ordering}, {fields.split(',')[0]} limit 21 offset %s",
                         (*values, start), as_dict=True)
    has_more = len(rows) > 20
    rows = rows[:20]
    if section == "inventory":
        for row in rows:
            row.available = balance(row.name, row.warehouse)["available"] if row.warehouse else None
            row.stock_status = "Archived" if row.disabled else (
                "Setup needed" if row.available is None else (
                    "Sold out" if row.lc_sold_out or row.available <= 0 else (
                        "Low stock" if row.available <= float(row.lc_low_stock or 0) else "In stock"
                    )
                )
            )
    return {"items": rows, "has_more": has_more, "start": start}


def set_accepting(shop, enabled):
    require_platform()
    doc = frappe.get_doc("LC Shop", shop)
    doc.accepting_orders = enabled in (True, 1, "1")
    doc.save()
    return {"name": doc.name, "accepting_orders": bool(doc.accepting_orders)}


def setup_options(search=""):
    require_platform()
    linked = frappe.get_all("LC Shop", pluck="company", limit_page_length=0)
    return {
        "country": frappe.db.get_single_value("Global Defaults", "country"),
        "currency": frappe.db.get_single_value("Global Defaults", "default_currency"),
        "countries": frappe.get_all("Country", pluck="name", order_by="name",
                                    limit_page_length=300),
        "currencies": frappe.get_all("Currency", filters={"enabled": 1}, pluck="name",
                                     order_by="name", limit_page_length=300),
        "companies": frappe.get_all("Company", filters={"name": ["not in", linked]}
                                    if linked else {}, pluck="name", order_by="name",
                                    limit_page_length=500),
        "users": frappe.get_all(
            "User", filters={"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]},
            or_filters={"full_name": ["like", f"%{str(search or '').strip()[:140]}%"],
                        "name": ["like", f"%{str(search or '').strip()[:140]}%"]},
            fields=["name", "full_name"], order_by="full_name asc, name asc",
            limit_page_length=20,
        ),
    }


def create_shop(shop_name, company="", country="", currency=""):
    require_platform()
    shop_name = str(shop_name or "").strip()
    if not 1 <= len(shop_name) <= 140:
        reject("Enter a shop name (up to 140 characters)")
    doc = frappe.get_doc({"doctype": "LC Shop", "shop_name": shop_name,
                          "company": company or None, "company_country": country or None,
                          "company_currency": currency or None, "status": "Draft"})
    doc.insert()
    return {"name": doc.name, "company": doc.company}


def save_membership(shop, user, membership_role="Driver", name="", enabled=1):
    require_platform()
    if membership_role not in {"Owner", "Staff", "Driver"}:
        reject("Choose Owner, Staff or Driver")
    if name:
        doc = frappe.get_doc("LC Shop Member", name)
        if doc.shop != shop or doc.user != user:
            reject("Shop and user cannot change when editing this membership")
    else:
        doc = frappe.get_doc({"doctype": "LC Shop Member", "shop": shop, "user": user})
    doc.membership_role = membership_role
    doc.enabled = enabled in (True, 1, "1")
    doc.save()
    return {"name": doc.name, "shop": doc.shop, "user": doc.user}
