"""Fish profit uses submitted invoices and ERPNext valuation, never today's prices."""

from datetime import timedelta

import frappe
from frappe.utils import getdate

from local_commerce.permissions.scope import require_shop
from local_commerce.services.fish import require_fish
from local_commerce.services.owner import reject


def report(shop, start_date, end_date):
    require_shop(shop, 'write')
    doc = frappe.get_doc('LC Shop', shop)
    require_fish(doc)
    try:
        start, end = getdate(start_date), getdate(end_date)
    except (ValueError, TypeError):
        reject('Choose valid report dates')
    if start > end or (end - start).days >= 366:
        reject('Choose a report period of up to 366 days')
    until = end + timedelta(days=1)
    sales = frappe.db.sql('''
        select x.item_code as item, sum(x.stock_qty) as sold_kg,
               sum(x.pieces) as sold_pieces, sum(x.revenue) as revenue,
               sum(coalesce(cost.amount, 0)) as cost
        from (
            select o.name as order_name, o.delivery_note, sii.item_code,
                   sum(sii.stock_qty) as stock_qty,
                   sum(case when sii.uom='Nos' then sii.qty else 0 end) as pieces,
                   sum(sii.base_net_amount) as revenue
            from `tabSales Invoice` si
            inner join `tabLC Order` o on o.name=si.lc_order and o.sales_invoice=si.name
            inner join `tabSales Invoice Item` sii on sii.parent=si.name
            inner join `tabItem` i on i.name=sii.item_code
            where o.shop=%s and i.stock_uom='Kg' and i.lc_shop=%s
              and si.company=%s and si.docstatus=1 and si.posting_date >= %s
              and si.posting_date < %s
            group by o.name, o.delivery_note, sii.item_code
        ) x
        left join (
            select sle.voucher_no, sle.item_code, -sum(sle.stock_value_difference) as amount
            from `tabStock Ledger Entry` sle
            where sle.voucher_type='Delivery Note' and sle.is_cancelled=0
              and sle.warehouse=%s and sle.company=%s
            group by sle.voucher_no, sle.item_code
        ) cost on cost.voucher_no=x.delivery_note and cost.item_code=x.item_code
        group by x.item_code
    ''', (shop, shop, doc.company, start, until, doc.warehouse, doc.company), as_dict=True)
    movements = frappe.db.sql('''
        select sle.item_code as item,
            sum(case when sle.posting_date < %s then sle.actual_qty else 0 end) as opening_kg,
            sum(case when sle.posting_date >= %s and sle.actual_qty > 0
                     then sle.actual_qty else 0 end) as stock_in_kg,
            sum(case when sle.posting_date >= %s and sle.actual_qty < 0
                     then -sle.actual_qty else 0 end) as stock_out_kg,
            sum(sle.actual_qty) as closing_kg,
            sum(sle.stock_value_difference) as closing_value
        from `tabStock Ledger Entry` sle inner join `tabItem` i on i.name=sle.item_code
        where i.lc_shop=%s and i.stock_uom='Kg' and sle.warehouse=%s and sle.company=%s
          and sle.is_cancelled=0 and sle.posting_date < %s
        group by sle.item_code
    ''', (start, start, start, shop, doc.warehouse, doc.company, until), as_dict=True)
    waste = frappe.db.sql('''
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
    ''', (shop, doc.warehouse, doc.company, start, until), as_dict=True)
    removals = frappe.db.sql('''
        select sle.item_code as item, -sum(sle.actual_qty) as removal_kg,
               -sum(sle.stock_value_difference) as removal_cost
        from `tabStock Ledger Entry` sle inner join (
            select distinct stock_entry from `tabLC Fish Movement`
            where shop=%s and kind='Remove' and stock_entry is not null
        ) removals on removals.stock_entry=sle.voucher_no
        where sle.voucher_type='Stock Entry' and sle.warehouse=%s and sle.company=%s
          and sle.is_cancelled=0 and sle.posting_date >= %s and sle.posting_date < %s
        group by sle.item_code
    ''', (shop, doc.warehouse, doc.company, start, until), as_dict=True)
    products = frappe.get_all('Item', filters={'lc_shop': shop, 'stock_uom': 'Kg'},
                              fields=['name', 'item_name'], limit_page_length=0)
    data = {row.name: {'item': row.name, 'item_name': row.item_name} for row in products}
    keys = ['sold_kg', 'sold_pieces', 'revenue', 'cost', 'opening_kg', 'stock_in_kg',
            'stock_out_kg', 'closing_kg', 'closing_value', 'wastage_kg', 'wastage_cost',
            'removal_kg', 'removal_cost']
    for records in (sales, movements, waste, removals):
        for row in records:
            if row.item in data:
                data[row.item].update({key: float(row.get(key) or 0) for key in keys if key in row})
    totals = dict.fromkeys(keys, 0.0)
    for row in data.values():
        for key in keys:
            row.setdefault(key, 0.0)
            totals[key] += row[key]
        row['gross_profit'] = row['revenue'] - row['cost']
        row['profit_after_wastage'] = row['gross_profit'] - row['wastage_cost']
        row['profit_after_stock_losses'] = row['profit_after_wastage'] - row['removal_cost']
    totals['gross_profit'] = totals['revenue'] - totals['cost']
    totals['profit_after_wastage'] = totals['gross_profit'] - totals['wastage_cost']
    totals['profit_after_stock_losses'] = totals['profit_after_wastage'] - totals['removal_cost']
    delivery = frappe.db.sql('''
        select coalesce(sum(t.base_tax_amount),0) from `tabSales Taxes and Charges` t
        inner join `tabSales Invoice` si on t.parent=si.name and t.parenttype='Sales Invoice'
        inner join `tabLC Order` o on o.name=si.lc_order and o.sales_invoice=si.name
        where o.shop=%s and si.company=%s and si.docstatus=1
          and si.posting_date >= %s and si.posting_date < %s
          and t.charge_type='Actual' and t.description='Delivery charge'
    ''', (shop, doc.company, start, until))[0][0]
    totals['delivery_revenue'] = float(delivery or 0)
    return {'start_date': str(start), 'end_date': str(end), 'totals': totals,
            'items': list(data.values()),
            'currency': frappe.db.get_value('Company', doc.company, 'default_currency'),
            'basis': 'Product revenue excludes taxes and delivery fees. Cost is ERPNext delivery '
                     'valuation matched to submitted invoices. Profit after wastage excludes '
                     'operating expenses, rider costs and cash differences. '
                     'Profit after stock losses also deducts other removals. Stock out includes '
                     'dispatches, removals and wastage; unbilled dispatches are not sales.'}
