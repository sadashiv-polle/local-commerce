"""Delivery-person arrival confirmation, once per customer order."""

import frappe
from frappe.utils import now_datetime

from local_commerce.services.owner import reject


def mark_arrived(order):
    from local_commerce.services import notifications, orders

    doc = frappe.get_doc("LC Order", order)

    def authorize():
        if doc.delivery_user != frappe.session.user or not orders.is_shop_driver(
            frappe.session.user, doc.shop
        ):
            frappe.throw("This delivery is not assigned to you", frappe.PermissionError)

    authorize()
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    frappe.db.sql("select name from `tabLC Order` where name=%s for update", doc.name)
    doc.reload()
    authorize()
    if doc.status != "Out for Delivery":
        reject("You can notify arrival only while this order is out for delivery")
    if not doc.get("arrived_at"):
        token = orders._order_operation.set(True)
        try:
            doc.arrived_at = now_datetime()
            doc.arrived_by = frappe.session.user
            doc.save(ignore_permissions=True)
            notifications.delivery_arrived(doc)
        finally:
            orders._order_operation.reset(token)
    return {"arrived_at": str(doc.arrived_at)}
