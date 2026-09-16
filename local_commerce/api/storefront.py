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
def category_menu():
    from local_commerce.services.category_menu import menu

    return menu()


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
