import frappe
from frappe.sessions import get_csrf_token

from local_commerce.permissions.policy import MEMBER_ROLES, is_platform
from local_commerce.permissions.scope import identity, memberships


def get_context():
    user, roles = identity()
    if user == "Guest":
        return {
            "user": "Guest",
            "full_name": "Guest",
            "roles": [],
            "platform_admin": False,
            "memberships": [],
            "capabilities": [],
            "csrf_token": get_csrf_token(),
        }
    platform = is_platform(user, roles)
    member_rows = [
        dict(m) for m in memberships(user) if MEMBER_ROLES.get(m.membership_role) in roles
    ]
    shop_names = sorted({member["shop"] for member in member_rows})
    companies = (
        {
            shop.name: shop.company
            for shop in frappe.get_all(
                "LC Shop", filters={"name": ["in", shop_names]}, fields=["name", "company"]
            )
        }
        if shop_names
        else {}
    )
    for member in member_rows:
        member["company"] = companies.get(member["shop"])
    return {
        "user": user,
        "full_name": frappe.db.get_value("User", user, "full_name") or user,
        "roles": [r for r in roles if r.startswith("LC ")],
        "platform_admin": platform,
        "memberships": member_rows,
        "capabilities": [],
        "release": "0.1.0",
        "csrf_token": get_csrf_token(),
    }
