"""Customer ratings for fulfilled Local Commerce orders."""

import frappe


def _score(value, label):
    try:
        score = int(value)
    except (TypeError, ValueError):
        frappe.throw(f"Choose a {label} rating from 1 to 5")
    if score < 1 or score > 5:
        frappe.throw(f"Choose a {label} rating from 1 to 5")
    return score


def serialize(row):
    return {
        "shop": row.shop_rating,
        "products": row.product_rating,
        "delivery": row.delivery_rating,
        "comment": row.comment or "",
        "created": str(row.creation),
    }


def submit(order, shop_rating, product_rating, delivery_rating, comment=""):
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Sign in to rate an order", frappe.PermissionError)
    doc = frappe.get_doc("LC Order", order)
    if doc.customer_user != user:
        frappe.throw("Only the customer who placed this order can rate it", frappe.PermissionError)
    if doc.status != "Delivered":
        frappe.throw("You can rate this order after it has been delivered")
    existing = frappe.db.get_value("LC Rating", {"order": doc.name, "customer": user}, "name")
    if existing:
        return serialize(frappe.get_doc("LC Rating", existing))
    text = (comment or "").strip()
    if len(text) > 1000:
        frappe.throw("Your review can contain up to 1,000 characters")
    rating = frappe.get_doc({
        "doctype": "LC Rating",
        "order": doc.name,
        "shop": doc.shop,
        "customer": user,
        "shop_rating": _score(shop_rating, "shop"),
        "product_rating": _score(product_rating, "product"),
        "delivery_rating": _score(delivery_rating, "delivery"),
        "comment": text,
    }).insert(ignore_permissions=True)
    return serialize(rating)
