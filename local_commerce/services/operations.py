"""Read-only operational queues and rider totals; never infer payment success."""
import math
import frappe
from frappe.utils import now_datetime
from local_commerce.permissions.scope import require_platform

ACTIVE = "('Requested','Accepted','Preparing','Ready','Picked Up','Out for Delivery')"
CONDITIONS = {
    'returns': "o.return_status in ('Requested','Reviewed','Refund queued','Refund processing','Needs review')",
    'unpaid': f"o.status in {ACTIVE} and o.payment_method in ('Cashfree','Manual UPI') and o.payment_status not in ('Paid','Reconciled','Refunded')",
    'refunds': "o.refund_attention=1 or (o.status='Cancelled' and o.payment_status in ('Paid','Collected','Reconciled') and coalesce(o.gateway_refunded_amount,0)=0)",
    'unassigned': "o.status='Ready' and coalesce(o.delivery_user,'')=''",
    'expired': "o.status in ('Requested','Accepted','Preparing','Ready') and exists (select 1 from `tabLC Fish Lot` l where l.shop=o.shop and l.expires_at<=%(now)s and JSON_SEARCH(IF(JSON_VALID(o.fish_allocations_json),o.fish_allocations_json,'[]'),'one',l.name,NULL,'$[*].lot') is not null)",
    'accounting': "coalesce(o.gateway_accounting_error,'')!='' or coalesce(o.gateway_settlement_error,'')!='' or exists (select 1 from `tabLC COD Collection` c where c.`order`=o.name and c.status='Difference Pending') or (o.status='Delivered' and coalesce(o.sales_invoice,'')='')",
}


def attention(category='unpaid', start=0, shop=''):
    require_platform()
    if category not in CONDITIONS:
        frappe.throw('Choose a valid attention category')
    start = max(0, int(start))
    params = dict(now=now_datetime(), shop=shop, start=start)
    scope = ' and o.shop=%(shop)s' if shop else ''
    counts = {}
    for key, condition in CONDITIONS.items():
        counts[key] = frappe.db.sql(f"select count(*) from `tabLC Order` o where ({condition}){scope}", params)[0][0]
    rows = frappe.db.sql(f"""select o.name, o.shop, s.shop_name, o.status,
        o.payment_status, o.payment_method, o.modified from `tabLC Order` o
        inner join `tabLC Shop` s on s.name=o.shop
        where ({CONDITIONS[category]}){scope}
        order by o.modified asc, o.name asc limit 21 offset %(start)s""", params, as_dict=True)
    return dict(counts=counts, items=rows[:20], has_more=len(rows)>20)


def rider_totals():
    from local_commerce.services.orders import driver_shops
    driver_shops(frappe.session.user)  # Role check; historical earnings remain owned by this rider.
    params = {'user': frappe.session.user}
    delivered = frappe.db.sql("""select o.shop, s.shop_name, so.currency,
        count(*) as deliveries, sum(coalesce(o.rider_fee_amount,0)) as earned,
        sum(case when coalesce(o.rider_fee_recorded,0)=0 then 1 else 0 end) as unrecorded
        from `tabLC Order` o join `tabLC Shop` s on s.name=o.shop
        join `tabSales Order` so on so.name=o.sales_order
        where o.delivery_user=%(user)s and o.status='Delivered'
        group by o.shop,s.shop_name,so.currency""", params, as_dict=True)
    cash = frappe.db.sql("""select c.shop,s.shop_name,c.currency,
        sum(c.collected_amount) as collected,
        sum(case when c.reconciled_at is null then c.collected_amount else 0 end) as due,
        sum(case when c.status='Difference Pending' then 1 else 0 end) as differences
        from `tabLC COD Collection` c join `tabLC Shop` s on s.name=c.shop
        where c.delivery_user=%(user)s group by c.shop,s.shop_name,c.currency""", params, as_dict=True)
    return dict(delivered=delivered, cash=cash)


def rider_rates(shop='', amount=None):
    require_platform()
    if amount is not None:
        value = float(amount)
        if not math.isfinite(value) or value < 0 or value > 100000:
            frappe.throw('Enter a rider fee between 0 and 100000')
        doc = frappe.get_doc('LC Shop', shop)
        doc.rider_delivery_fee = value
        doc.save()
    return frappe.db.sql("""select s.name,s.shop_name,s.rider_delivery_fee,c.default_currency as currency
        from `tabLC Shop` s join `tabCompany` c on c.name=s.company order by s.shop_name""", as_dict=True)
