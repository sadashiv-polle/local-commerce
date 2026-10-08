import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import storefront


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def featured():
    return storefront.featured()


@frappe.whitelist(methods=["GET"])
def settings():
    return storefront.settings()


@frappe.whitelist(methods=["POST"])
def configure(mode, title="Picked for you", random_count=6, products=None):
    return storefront.configure(mode, title, random_count, products)


@frappe.whitelist(methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def product_options(search="", start=0):
    return storefront.product_options(search, start)


@frappe.whitelist(methods=["GET"])
def saved_lists():
    return storefront.saved_lists()


@frappe.whitelist(methods=["GET"])
def get_list(name):
    return storefront.get_list(name)


@frappe.whitelist(methods=["POST"])
def save_list(mode, title, name="", random_count=6, products=None):
    return storefront.save_list(name, mode, title, random_count, products)


@frappe.whitelist(methods=["POST"])
def toggle_list(name, enabled):
    return storefront.toggle_list(name, enabled)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=120, seconds=3600)
def recommendations(address=""):
    from local_commerce.services.recommendations import suggestions

    return suggestions(address)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def category_menu(available_only=0):
    from local_commerce.services.category_menu import menu

    return menu(available_only=str(available_only) == "1")


@frappe.whitelist(methods=["GET"])
def category_settings():
    from local_commerce.services.category_menu import menu

    return menu(admin=True)


@frappe.whitelist(methods=["POST"])
def save_categories(enabled, categories):
    from local_commerce.services.category_menu import save_menu

    return save_menu(enabled, categories)


@frappe.whitelist(methods=["POST"])
def upload_category_image():
    from local_commerce.services.category_menu import upload_image

    return upload_image()


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=600, seconds=3600)
def discover(search="", address="", start=0):
    from local_commerce.services.home_discovery import discover

    return discover(search, address, start)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=3600)
def promotions():
    from local_commerce.services.promotions import get
    return get()


@frappe.whitelist(methods=["GET"])
def promotion_settings():
    from local_commerce.services.promotions import get
    return get(admin=True)


@frappe.whitelist(methods=["POST"])
def save_promotions(config):
    from local_commerce.services.promotions import save
    return save(config)


@frappe.whitelist(methods=["POST"])
def upload_promotion_image():
    from local_commerce.services.category_menu import upload_image
    return upload_image()


@frappe.whitelist(methods=["GET"])
def shop_priority_settings():
    from local_commerce.permissions.scope import require_platform
    require_platform()
    return {
        "pinned_shop": frappe.get_single("LC Store Settings").get("pinned_shop") or "",
        "shops": frappe.get_all("LC Shop", filters={"status": "Active"},
                                fields=["name", "shop_name"], order_by="shop_name, name",
                                limit_page_length=1000),
    }


@frappe.whitelist(methods=["POST"])
def save_shop_priority(pinned_shop=""):
    from local_commerce.permissions.scope import require_platform
    require_platform()
    if pinned_shop and not frappe.db.exists("LC Shop", {"name": pinned_shop, "status": "Active"}):
        frappe.throw("Choose an active shop")
    doc = frappe.get_single("LC Store Settings")
    doc.pinned_shop = pinned_shop or ""
    doc.save()
    return {"pinned_shop": doc.pinned_shop}


@frappe.whitelist(methods=["GET"])
def branding_settings():
    from local_commerce.services.branding import settings
    return settings()


@frappe.whitelist(methods=["POST"])
def upload_favicon():
    from local_commerce.services.branding import upload
    return upload()


@frappe.whitelist(methods=["POST"])
def reset_favicon():
    from local_commerce.services.branding import reset
    return reset()
