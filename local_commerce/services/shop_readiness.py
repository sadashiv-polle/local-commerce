"""Read-only setup checks; never enable a shop or bypass checkout validation."""
import frappe
from local_commerce.permissions.scope import require_platform
from local_commerce.services.shop_hours import normalize
from local_commerce.services.locations import shop_location


def readiness(shop):
    require_platform()
    doc = frappe.get_doc("LC Shop", shop)
    checks = []

    def add(label, ready, detail, target="settings"):
        checks.append(dict(label=label, ready=bool(ready), detail=detail, target=target))

    def account(name, root):
        return bool(name and frappe.db.exists("Account", {
            "name": name, "company": doc.company, "is_group": 0,
            "disabled": 0, "root_type": root,
        }))

    def member(role, user_role):
        users = frappe.get_all("LC Shop Member", filters={"shop": shop, "enabled": 1,
                                                       "membership_role": role}, pluck="user")
        return any(frappe.db.get_value("User", user, "enabled") and
                   user_role in frappe.get_roles(user) for user in users)

    add("Shop active and accepting orders", doc.status == "Active" and doc.accepting_orders,
        "Both Active status and Accept new orders must be enabled.")
    add("Owner assigned", member("Owner", "LC Shop Owner"),
        "Needs an enabled owner login, role and shop membership.", "people")
    add("Delivery person assigned", member("Delivery Person", "LC Delivery Person"),
        "Needs an enabled rider login, role and shop membership. Assign orders separately.", "people")
    add("Location and delivery radius", shop_location(doc) and float(doc.service_radius_km or 0) > 0,
        "Save a valid shop map pin and a positive delivery radius.")
    warehouse = doc.warehouse and frappe.db.exists("Warehouse", {"name": doc.warehouse,
        "company": doc.company, "disabled": 0, "is_group": 0})
    cost = doc.cost_center and frappe.db.exists("Cost Center", {"name": doc.cost_center,
        "company": doc.company, "disabled": 0, "is_group": 0})
    add("Inventory accounts and warehouse", warehouse and cost and
        account(doc.stock_adjustment_account, "Expense") and doc.selling_price_list,
        "Needs a same-company warehouse, cost center, stock adjustment expense account and price list.", "inventory")
    payment = bool((doc.cod_enabled and doc.cod_cash_account and doc.cod_mode_of_payment) or
                   (doc.upi_enabled and doc.upi_id and doc.upi_bank_account and doc.upi_mode_of_payment) or
                   (doc.cashfree_enabled and doc.cashfree_gateway and doc.cashfree_clearing_account and doc.cashfree_mode_of_payment))
    add("Payment method configured", payment,
        "Checks required selections for at least one enabled method; verify real payments separately.")
    add("Delivery mode enabled", doc.delivery_enabled or doc.scheduled_enabled,
        "Enable Normal delivery, Scheduled delivery, or both.")
    if doc.delivery_enabled:
        try:
            hours = normalize(doc.opening_hours_json)
            valid_hours = not hours or any(row["enabled"] for row in hours)
        except (ValueError, TypeError):
            valid_hours = False
        add("Normal ordering hours", valid_hours,
            "At least one day must allow ordering. No saved hours means unrestricted hours; this does not mean open right now.")
    if doc.scheduled_enabled:
        daily = frappe.db.exists("LC Delivery Schedule", {"shop": shop, "enabled": 1})
        dated = frappe.db.exists("LC Delivery Slot", {"shop": shop, "enabled": 1,
            "archived": 0, "ordering_end": [">", frappe.utils.now_datetime()]})
        add("Scheduled slots configured", daily or dated,
            "Needs an enabled daily schedule or future booking slot. Capacity and generation still need checking.")
    from local_commerce.services.owner import catalog
    # Bound the inspection; don't claim that unchecked products are unavailable.
    result = catalog(shop, status="Active")
    items = result["items"]
    usable = any(not row["lc_sold_out"] and float(row["stock"]["available"] or 0) > 0
                 and row["price"] is not None and float(row["price"]) > 0 for row in items)
    add("Priced product with sellable stock", usable,
        f"Checked {len(items)} of {result['total']} active products using stock reservations and fish expiry rules. "
        "Review remaining products and selling options in Products & stock.", "inventory")
    return {"checks": checks, "passed": sum(row["ready"] for row in checks), "total": len(checks)}
