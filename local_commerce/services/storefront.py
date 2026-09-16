import frappe

from local_commerce.permissions.scope import require_platform
from local_commerce.services.orders import public_product
from local_commerce.services.owner import reject


def validate_settings(doc):
    if doc.mode not in {"Disabled", "Selected", "Random"}:
        reject("Choose Disabled, Selected or Random")
    if not 1 <= int(doc.random_count or 0) <= 24:
        reject("Choose 1 to 24 random products")
    if len(doc.products) > 24:
        reject("Select up to 24 featured products")
    names = [row.item for row in doc.products]
    if len(set(names)) != len(names):
        reject("A product can only be selected once")
    for name in names if doc.mode == "Selected" else []:
        shop = frappe.db.get_value("Item", name, "lc_shop")
        if not shop:
            reject("Select products belonging to a shop")
        public_product(shop, name)
    doc.title = str(doc.title or "Picked for you").strip()[:80]


def settings():
    require_platform()
    doc = frappe.get_single("LC Store Settings")
    return {
        "mode": doc.mode or "Disabled",
        "title": doc.title or "Picked for you",
        "random_count": doc.random_count or 6,
        "products": [
            {
                "item": row.item,
                "item_name": frappe.db.get_value("Item", row.item, "item_name") or row.item,
            }
            for row in doc.products
        ],
    }


def configure(mode, title="Picked for you", random_count=6, products=None):
    require_platform()
    doc = frappe.get_single("LC Store Settings")
    names = frappe.parse_json(products) if isinstance(products, str) else products
    if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
        reject("Select a list of products")
    try:
        count = int(random_count)
    except (ValueError, TypeError):
        reject("Choose a whole number from 1 to 24")
    if str(random_count) not in {str(count), f"{count}.0"}:
        reject("Choose a whole number from 1 to 24")
    doc.update({"mode": mode, "title": title, "random_count": count})
    doc.set("products", [{"item": name} for name in names])
    doc.save()
    return settings()


def featured():
    doc = frappe.get_single("LC Store Settings")
    if doc.mode not in {"Selected", "Random"}:
        return {"title": doc.title or "Picked for you", "items": []}
    names = [row.item for row in doc.products]
    if doc.mode == "Random":
        names = frappe.db.sql(
            """select i.name from `tabItem` i inner join `tabLC Shop` s on s.name=i.lc_shop
            where s.status='Active' and i.disabled=0 and i.is_stock_item=1
            and i.has_variants=0 and coalesce(i.variant_of, '')=''
            and i.has_batch_no=0 and i.has_serial_no=0
            order by rand() limit %s""",
            (min(24, max(1, int(doc.random_count or 6))),),
            pluck=True,
        )
    result = []
    for name in names[:24]:
        item = frappe.db.get_value("Item", name, ["lc_shop", "disabled", "item_name"], as_dict=True)
        if not item or item.disabled:
            continue
        shop_name = frappe.db.get_value(
            "LC Shop", {"name": item.lc_shop, "status": "Active"}, "shop_name"
        )
        if not shop_name:
            continue
        try:
            product = public_product(item.lc_shop, name)
        except frappe.ValidationError:
            continue
        result.append({**product, "shop": item.lc_shop, "shop_name": shop_name})
    return {"title": doc.title or "Picked for you", "items": result}
