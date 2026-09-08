import frappe

from local_commerce.permissions.policy import can_access_shop, is_platform


def identity(user=None):
    user = user or frappe.session.user
    return user, frappe.get_roles(user)


def memberships(user):
    if user == "Guest":
        return []
    # Internal authorization lookup; caller cannot supply filters or another user.
    return frappe.get_all(
        "LC Shop Member",
        filters={"user": user, "enabled": 1},
        fields=["shop", "user", "membership_role", "enabled"],
    )


def shop_permission(doc, user=None, permission_type=None, **kwargs):
    user, roles = identity(user)
    return can_access_shop(user, roles, memberships(user), doc.name, permission_type or "read")


def shop_query(user=None):
    user, roles = identity(user)
    if is_platform(user, roles):
        return ""
    rows = memberships(user)
    shops = sorted({m.shop for m in rows if can_access_shop(user, roles, rows, m.shop)})
    if not shops:
        return "1=0"
    return "`tabLC Shop`.`name` in (" + ",".join(frappe.db.escape(s) for s in shops) + ")"


def member_permission(doc, user=None, permission_type=None, **kwargs):
    user, roles = identity(user)
    return is_platform(user, roles)


def member_query(user=None):
    user, roles = identity(user)
    return "" if is_platform(user, roles) else "1=0"


def require_platform():
    user, roles = identity()
    if not is_platform(user, roles):
        frappe.throw("Platform administrator access required", frappe.PermissionError)


def require_shop(shop, permission="read"):
    user, roles = identity()
    if not can_access_shop(user, roles, memberships(user), shop, permission):
        frappe.throw("Shop access denied", frappe.PermissionError)
