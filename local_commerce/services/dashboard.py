"""Shop-scoped operational summary, with delivered sales kept separate from requests."""

from datetime import timedelta

import frappe
from frappe.utils import getdate, nowdate

from local_commerce.permissions.scope import require_shop
from local_commerce.services.dashboard_rules import period_start
from local_commerce.services.owner import balance, reject


def summary(shop, period="today"):
    require_shop(shop, "write")
    doc = frappe.get_doc("LC Shop", shop)
    today = getdate(nowdate())
    try:
        since = period_start(period, today)
    except ValueError as exc:
        reject(str(exc))
    until = today + timedelta(days=1)
    sales = frappe.db.sql(
        """select count(*) as delivered_orders, coalesce(sum(so.grand_total), 0) as sales
        from `tabLC Order` o inner join `tabSales Order` so on so.name=o.sales_order
        where o.shop=%s and o.status='Delivered' and o.delivered_at >= %s
        and o.delivered_at < %s""",
        (shop, since, until),
        as_dict=True,
    )[0]
    received = frappe.db.count("LC Order", {"shop": shop, "creation": ["between", [since, until]]})
    pending = frappe.db.count("LC Order", {"shop": shop, "status": "Requested"})
    active = frappe.db.count(
        "LC Order", {"shop": shop, "status": ["not in", ["Delivered", "Cancelled"]]}
    )
    cash = frappe.db.sql(
        """select currency, count(*) as collections, sum(collected_amount) as amount
        from `tabLC COD Collection` where shop=%s and status='Awaiting Handover'
        group by currency""",
        (shop,),
        as_dict=True,
    )
    products = frappe.get_all(
        "Item",
        filters={"lc_shop": shop, "disabled": 0, "is_stock_item": 1},
        fields=["name", "item_name", "lc_sold_out", "lc_low_stock", "stock_uom"],
        limit_page_length=0,
    )
    low, sold = [], []
    from local_commerce.services.fish import sellable

    for item in products:
        available = balance(item.name, doc.warehouse)["available"] if doc.warehouse else None
        if available is not None:
            available = sellable(doc, item, available)
        row = {
            "name": item.name,
            "item_name": item.item_name,
            "available": available,
            "uom": item.stock_uom,
        }
        if item.lc_sold_out or (available is not None and available <= 0):
            sold.append(row)
        elif available is not None and available <= float(item.lc_low_stock or 0):
            low.append(row)
    return {
        "period": period,
        "since": str(since),
        "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
        "sales": float(sales.sales),
        "delivered_orders": sales.delivered_orders,
        "received_orders": received,
        "pending_orders": pending,
        "active_orders": active,
        "cash_pending": cash,
        "low_stock_count": len(low),
        "sold_out_count": len(sold),
        "low_stock": low[:8],
        "sold_out": sold[:8],
        "inventory_configured": bool(doc.warehouse),
    }
