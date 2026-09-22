"""Pure authorization decisions, also exercised without a running Bench."""

PLATFORM_ROLE = "LC Platform Administrator"
MEMBER_ROLES = {
    "Owner": "LC Shop Owner", "Staff": "LC Shop Staff",
    "Delivery Person": "LC Delivery Person",
}


def is_platform(user, roles):
    return user != "Guest" and (user == "Administrator" or PLATFORM_ROLE in roles)


def can_access_shop(user, roles, memberships, shop, permission="read"):
    if user == "Guest":
        return False
    if is_platform(user, roles):
        return True
    if permission not in {"read", "write"}:
        return False
    allowed = {"Owner", "Staff"} if permission == "read" else {"Owner"}
    return any(
        m["shop"] == shop
        and m["membership_role"] in allowed
        and MEMBER_ROLES.get(m["membership_role"]) in roles
        and m["enabled"]
        and m["user"] == user
        for m in memberships
    )


SCHEDULE_ROLE = "LC Scheduled Delivery Manager"


def can_manage_schedule(user, roles, memberships, shop):
    return is_platform(user, roles) or (
        SCHEDULE_ROLE in roles and can_access_shop(user, roles, memberships, shop, "write")
    )
