"""Fish profit uses submitted invoices and ERPNext valuation, never today's prices."""

from datetime import timedelta

import frappe
from frappe.utils import getdate

from local_commerce.permissions.scope import require_shop
from local_commerce.services.fish import require_fish
from local_commerce.services.owner import reject


def report(shop, start_date, end_date):
    require_shop(shop, "write")
    doc = frappe.get_doc("LC Shop", shop)
    require_fish(doc)
    try:
        start, end = getdate(start_date), getdate(end_date)
    except (ValueError, TypeError):
        reject("Choose valid report dates")
    if start > end or (end - start).days >= 366:
        reject("Choose a report period of up to 366 days")
    until = end + timedelta(days=1)
    # Read invoice lines independently from stock rows: joining the two directly
    # duplicates cost for multiple invoice lines and partially billed deliveries.
    invoices = frappe.db.sql(
        """
        select si.name as invoice, si.update_stock, si.is_return, si.return_against,
               sii.name as detail, sii.item_code as item, sii.stock_qty,
               sii.uom, sii.qty, sii.base_net_amount as revenue,
               sii.delivery_note, sii.dn_detail, o.delivery_note as order_delivery
        from `tabSales Invoice` si
        inner join `tabSales Invoice Item` sii on sii.parent=si.name
        inner join `tabItem` i on i.name=sii.item_code
        left join `tabLC Order` o on o.name=si.lc_order and o.shop=%s
        where i.lc_shop=%s and i.stock_uom in ('Kg','Nos')
          and si.company=%s and si.docstatus=1
          and (sii.warehouse=%s or o.name is not null)
          and si.posting_date >= %s and si.posting_date < %s
    """,
        (shop, shop, doc.company, doc.warehouse, start, until),
        as_dict=True,
    )
    stock_costs = frappe.db.sql(
        """
        select voucher_type, voucher_no, voucher_detail_no, item_code as item,
               sum(actual_qty) as quantity, -sum(stock_value_difference) as cost
        from `tabStock Ledger Entry`
        where warehouse=%s and company=%s and is_cancelled=0
          and voucher_type in ('Delivery Note','Sales Invoice')
        group by voucher_type, voucher_no, voucher_detail_no, item_code
    """,
        (doc.warehouse, doc.company),
        as_dict=True,
    )
    sales = invoice_results(invoices, stock_costs)
    movements = frappe.db.sql(
        """
        select sle.item_code as item,
            sum(case when sle.posting_date < %s then sle.actual_qty else 0 end) as opening_kg,
            sum(case when sle.posting_date >= %s and sle.actual_qty > 0
                     then sle.actual_qty else 0 end) as stock_in_kg,
            sum(case when sle.posting_date >= %s and sle.actual_qty < 0
                     then -sle.actual_qty else 0 end) as stock_out_kg,
            sum(sle.actual_qty) as closing_kg,
            sum(sle.stock_value_difference) as closing_value
        from `tabStock Ledger Entry` sle inner join `tabItem` i on i.name=sle.item_code
        where i.lc_shop=%s and i.stock_uom in ('Kg', 'Nos') and sle.warehouse=%s and sle.company=%s
          and sle.is_cancelled=0 and sle.posting_date < %s
        group by sle.item_code
    """,
        (start, start, start, shop, doc.warehouse, doc.company, until),
        as_dict=True,
    )
    waste = frappe.db.sql(
        """
        select sle.item_code as item, -sum(sle.actual_qty) as wastage_kg,
               -sum(sle.stock_value_difference) as wastage_cost
        from `tabStock Ledger Entry` sle
        inner join (
            select distinct stock_entry from `tabLC Fish Movement`
            where shop=%s and kind='Wastage' and stock_entry is not null
        ) waste on waste.stock_entry=sle.voucher_no
        where sle.voucher_type='Stock Entry' and sle.warehouse=%s and sle.company=%s
          and sle.is_cancelled=0 and sle.posting_date >= %s and sle.posting_date < %s
        group by sle.item_code
    """,
        (shop, doc.warehouse, doc.company, start, until),
        as_dict=True,
    )
    removals = frappe.db.sql(
        """
        select sle.item_code as item, -sum(sle.actual_qty) as removal_kg,
               -sum(sle.stock_value_difference) as removal_cost
        from `tabStock Ledger Entry` sle inner join (
            select distinct stock_entry from `tabLC Fish Movement`
            where shop=%s and kind='Remove' and stock_entry is not null
        ) removals on removals.stock_entry=sle.voucher_no
        where sle.voucher_type='Stock Entry' and sle.warehouse=%s and sle.company=%s
          and sle.is_cancelled=0 and sle.posting_date >= %s and sle.posting_date < %s
        group by sle.item_code
    """,
        (shop, doc.warehouse, doc.company, start, until),
        as_dict=True,
    )
    products = frappe.get_all(
        "Item",
        filters={"lc_shop": shop, "stock_uom": ["in", ["Kg", "Nos"]]},
        fields=["name", "item_name", "stock_uom"],
        limit_page_length=0,
    )
    data = {
        row.name: {"item": row.name, "item_name": row.item_name, "stock_uom": row.stock_uom}
        for row in products
    }
    keys = [
        "sold_kg",
        "sold_pieces",
        "revenue",
        "cost",
        "opening_kg",
        "stock_in_kg",
        "stock_out_kg",
        "closing_kg",
        "closing_value",
        "wastage_kg",
        "wastage_cost",
        "removal_kg",
        "removal_cost",
        "pending_cost_lines",
        "pending_cost_revenue",
    ]
    for records in (sales, movements, waste, removals):
        for row in records:
            if row.item in data:
                data[row.item].update({key: float(row.get(key) or 0) for key in keys if key in row})
    quantity_fields = ["opening", "stock_in", "stock_out", "closing", "wastage", "removal"]
    keys += [f"{field}_pieces" for field in quantity_fields]
    totals = dict.fromkeys(keys, 0.0)
    for row in data.values():
        for field in [*quantity_fields, "sold"]:
            raw = float(row.get(f"{field}_kg") or 0)
            row[f"{field}_quantity"] = raw
            if row["stock_uom"] == "Nos":
                row[f"{field}_pieces"] = raw
                row[f"{field}_kg"] = 0.0
        for key in keys:
            row.setdefault(key, 0.0)
            totals[key] += row[key]
        row["gross_profit"] = row["revenue"] - row["cost"]
        row["profit_after_wastage"] = row["gross_profit"] - row["wastage_cost"]
        row["profit_after_stock_losses"] = row["profit_after_wastage"] - row["removal_cost"]
    totals["gross_profit"] = totals["revenue"] - totals["cost"]
    totals["profit_after_wastage"] = totals["gross_profit"] - totals["wastage_cost"]
    totals["profit_after_stock_losses"] = totals["profit_after_wastage"] - totals["removal_cost"]
    for row in [*data.values(), totals]:
        if row["pending_cost_lines"]:
            for key in ("gross_profit", "profit_after_wastage", "profit_after_stock_losses"):
                row[key] = None
    delivery = frappe.db.sql(
        """
        select coalesce(sum(t.base_tax_amount),0) from `tabSales Taxes and Charges` t
        inner join `tabSales Invoice` si on t.parent=si.name and t.parenttype='Sales Invoice'
        where si.company=%s and si.docstatus=1
          and exists (select 1 from `tabSales Invoice Item` sii
                      inner join `tabItem` i on i.name=sii.item_code
                      where sii.parent=si.name and i.lc_shop=%s)
          and not exists (select 1 from `tabSales Invoice Item` sii
                          inner join `tabItem` i on i.name=sii.item_code
                          where sii.parent=si.name and coalesce(i.lc_shop,'')<>%s)
          and si.posting_date >= %s and si.posting_date < %s
          and t.charge_type='Actual' and t.description='Delivery charge'
    """,
        (doc.company, shop, shop, start, until),
    )[0][0]
    totals["delivery_revenue"] = float(delivery or 0)
    return {
        "start_date": str(start),
        "end_date": str(end),
        "totals": totals,
        "items": list(data.values()),
        "currency": frappe.db.get_value("Company", doc.company, "default_currency"),
        "basis": "Submitted online and offline Sales Invoices and credit notes, by invoice date. "
        "Product revenue excludes taxes and delivery fees. Actual stock valuation is "
        "allocated to invoiced quantities; profit is unavailable while stock cost is pending. "
        "Credit notes without a stock return reduce revenue only. "
        "Profit excludes operating expenses, gateway fees, rider costs and cash differences. "
        "Stock movements follow their own posting dates. Mixed-shop delivery fees are excluded.",
    }


def invoice_results(invoices, stock_costs):
    """Allocate native valuation once per invoiced quantity; never assume missing cost is zero."""
    from collections import defaultdict

    costs = defaultdict(lambda: [0.0, 0.0])
    remaining = defaultdict(lambda: [0.0, 0.0])
    for row in invoices:
        source = row.get("return_against") if row["is_return"] else row["invoice"]
        if source:
            remaining[(source, row["item"])][0] += float(row["stock_qty"] or 0)
            remaining[(source, row["item"])][1] += float(row["revenue"] or 0)
    for row in stock_costs:
        for detail in dict.fromkeys((row.get("voucher_detail_no"), None)):
            # The None key supports older online invoices mapped from Sales Order.
            key = (row["voucher_type"], row["voucher_no"], detail, row["item"])
            costs[key][0] += float(row["quantity"] or 0)
            costs[key][1] += float(row["cost"] or 0)
    result = {}
    for row in invoices:
        item = row["item"]
        out = result.setdefault(
            item,
            frappe._dict(
                item=item,
                sold_kg=0,
                sold_pieces=0,
                revenue=0,
                cost=0,
                pending_cost_lines=0,
                pending_cost_revenue=0,
            ),
        )
        qty = float(row["stock_qty"] or 0)
        out["sold_kg"] += qty
        out["sold_pieces"] += float(row["qty"] or 0) if row["uom"] == "Nos" else 0
        out["revenue"] += float(row["revenue"] or 0)
        if row["update_stock"]:
            key = ("Sales Invoice", row["invoice"], row["detail"], item)
        elif row.get("delivery_note"):
            key = ("Delivery Note", row["delivery_note"], row.get("dn_detail"), item)
        elif row["is_return"]:
            # Financial credit only: original goods have not been returned to inventory.
            continue
        else:
            key = ("Delivery Note", row.get("order_delivery"), None, item)
        cost = costs.get(key)
        if row["is_return"] and not row["update_stock"] and (not cost or cost[0] <= 0):
            continue
        if not qty:
            continue
        if not cost or not cost[0] or qty * cost[0] >= 0:
            balance = remaining[(row["invoice"], item)]
            if not row["is_return"] and abs(balance[0]) < 0.000001 and abs(balance[1]) < 0.005:
                # Fully credited, unshipped goods have no delivery cost to await.
                continue
            out["pending_cost_lines"] += 1
            out["pending_cost_revenue"] += float(row["revenue"] or 0)
        else:
            out["cost"] += cost[1] * abs(qty / cost[0])
    return list(result.values())
