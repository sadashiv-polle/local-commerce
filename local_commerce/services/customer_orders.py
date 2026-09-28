"""Customer-scoped order search; classify before pagination, never hide failed payments."""

import frappe

from local_commerce.services.owner import reject

STATUSES = {
    "Requested",
    "Accepted",
    "Preparing",
    "Ready",
    "Picked Up",
    "Out for Delivery",
    "Delivered",
    "Cancelled",
}
GROUP = """case when o.status = 'Delivered' then 'delivered'
    when o.status = 'Cancelled'
      or o.payment_status in ('Failed', 'Payment Rejected', 'Refunded')
      or coalesce(o.gateway_accounting_error, '') != '' then 'attention'
    else 'pending' end"""


def find_orders(user, view, start, status=None, search=""):
    if view not in {"pending", "delivered", "attention"} or (status and status not in STATUSES):
        reject("Invalid customer order filter")
    if not isinstance(search, str) or len(search) > 100:
        reject("Search must be at most 100 characters")
    where = "o.customer_user = %s"
    values = [user]
    if status:
        where += " and o.status = %s"
        values.append(status)
    if search.strip():
        # Treat wildcard characters literally, including in partial order IDs.
        pattern = (
            "%" + search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        )
        where += """ and (o.name like %s escape '!'
            or exists (select 1 from `tabLC Shop` s where s.name=o.shop
                       and s.shop_name like %s escape '!')
            or exists (select 1 from `tabSales Order Item` i where i.parent=o.sales_order
                       and i.item_name like %s escape '!'))"""
        values.extend([pattern] * 3)
    counts = {"pending": 0, "delivered": 0, "attention": 0}
    for row in frappe.db.sql(
        f"select {GROUP} as bucket, count(*) as total "
        f"from `tabLC Order` o where {where} group by bucket",
        tuple(values),
        as_dict=True,
    ):
        counts[row.bucket] = row.total
    names = frappe.db.sql(
        f"""select o.name from `tabLC Order` o where {where} and ({GROUP}) = %s
            order by o.creation desc, o.name desc limit 20 offset %s""",
        tuple([*values, view, start]),
        pluck=True,
    )
    return names, counts
