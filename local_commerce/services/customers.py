"""Authenticated identity resolution; never match a customer from guest-supplied IDs."""

from contextvars import ContextVar

import frappe
from frappe.utils import validate_email_address

from local_commerce.permissions.policy import is_platform
from local_commerce.permissions.scope import identity
from local_commerce.services.owner import _owner_operation, reject

_linking_customer = ContextVar("lc_linking_customer", default=False)


def ensure_customer():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please sign in", frappe.AuthenticationError)
    # Serialize account creation across shops and concurrent browser tabs.
    frappe.db.sql("select name from `tabUser` where name=%s for update", user)
    linked = frappe.db.get_value("LC Customer Account", user, "customer")
    if linked:
        return summary(linked)
    account = frappe.get_doc("User", user)
    if not account.enabled:
        frappe.throw("Account is disabled", frappe.PermissionError)
    email = (account.name if "@" in account.name else account.email or "").strip().lower()
    candidates = set(
        frappe.get_all(
            "Portal User",
            filters={"user": user, "parenttype": "Customer", "parentfield": "portal_users"},
            pluck="parent",
            limit_page_length=3,
        )
    )
    if len(candidates) > 1:
        reject("Multiple Customers are linked to this login. Contact support.")
    if not candidates:
        # Email ownership comes from Frappe authentication (signup requires emailed
        # password setup), never from address form or a submitted phone number.
        rows = frappe.db.sql(
            """
            select distinct c.name from `tabCustomer` c
            left join `tabDynamic Link` dl on dl.link_doctype='Customer'
                and dl.link_name=c.name and dl.parenttype='Contact'
            left join `tabContact Email` ce on ce.parent=dl.parent and ce.parenttype='Contact'
            where lower(c.email_id)=%s or lower(ce.email_id)=%s limit 3
        """,
            (email, email),
            as_dict=True,
        )
        candidates = {r.name for r in rows}
        if len(candidates) > 1:
            reject(
                "Multiple Customers match this email. Contact support; no duplicate was created."
            )
        if candidates:
            match = frappe.get_doc("Customer", next(iter(candidates)))
            if match.customer_type != "Individual" or match.portal_users:
                reject("Contact support to verify this Customer link; no duplicate was created.")
    if not candidates:
        # Reuse the earliest Customer created by the previous per-shop implementation.
        # Historical orders remain attached to their original records; do not merge data.
        old = frappe.db.sql(
            """
            select so.customer from `tabLC Order` o
            inner join `tabSales Order` so on so.name=o.sales_order
            where o.customer_user=%s order by o.creation asc limit 1
        """,
            user,
        )
        if old:
            candidates = {old[0][0]}
    token = _linking_customer.set(True)
    owner_token = _owner_operation.set(True)
    try:
        if candidates:
            name = next(iter(candidates))
            frappe.db.sql("select name from `tabCustomer` where name=%s for update", name)
            existing_link = frappe.db.get_value("LC Customer Account", {"customer": name}, "user")
            if existing_link and existing_link != user:
                reject("This Customer is already linked to another login. Contact support.")
            customer = frappe.get_doc("Customer", name)
        else:
            group = frappe.db.get_single_value("Selling Settings", "customer_group")
            territory = frappe.db.get_single_value("Selling Settings", "territory")
            if not group or not territory:
                reject("Set default Customer Group and Territory in Selling Settings")
            customer = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": account.full_name or email,
                    "customer_type": "Individual",
                    "customer_group": group,
                    "territory": territory,
                    "email_id": validate_email_address(email, throw=True),
                }
            )
        if customer.disabled:
            reject("This Customer account is disabled. Contact support.")
        if not any(row.user == user for row in customer.get("portal_users", [])):
            if customer.get("portal_users"):
                reject("This Customer is already assigned to another login. Contact support.")
            customer.append("portal_users", {"user": user})
        customer.save(ignore_permissions=True)
        frappe.get_doc(
            {"doctype": "LC Customer Account", "user": user, "customer": customer.name}
        ).insert(ignore_permissions=True)
        account.reload()
        # Do not turn unrelated ERPNext staff into restricted LC tenants.
        if account.user_type == "Website User" or any(
            r.role.startswith("LC ") for r in account.roles
        ):
            account.add_roles("LC Customer")
        return summary(customer.name)
    finally:
        _owner_operation.reset(owner_token)
        _linking_customer.reset(token)


def summary(name):
    row = frappe.db.get_value("Customer", name, ["name", "customer_name", "disabled"], as_dict=True)
    if not row or row.disabled:
        reject("This Customer account is unavailable. Contact support.")
    return {"name": row.name, "customer_name": row.customer_name}


def account_info(start=0):
    from local_commerce.services.orders import offset

    customer = ensure_customer()
    history = frappe.get_all(
        "Sales Order",
        filters={"customer": customer["name"]},
        fields=["name", "transaction_date", "status", "grand_total", "currency"],
        order_by="creation desc",
        start=offset(start),
        limit_page_length=20,
    )
    return {"customer": customer, "orders": history}


def permission(doc, user=None, permission_type=None, **kwargs):
    user, roles = identity(user)
    return (
        permission_type in (None, "read")
        and user != "Guest"
        and (doc.user == user or is_platform(user, roles))
    )


def query(user=None):
    user, roles = identity(user)
    if is_platform(user, roles):
        return ""
    return "1=0" if user == "Guest" else "`tabLC Customer Account`.`user`=" + frappe.db.escape(user)
