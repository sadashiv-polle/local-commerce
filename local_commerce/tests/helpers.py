import frappe


def create_company():
    suffix = frappe.generate_hash(length=8)
    return frappe.get_doc(
        {
            "doctype": "Company",
            "company_name": "LC Test " + suffix,
            "abbr": suffix,
            "default_currency": "USD",
            "country": "United States",
        }
    ).insert()


def create_user(role):
    email = "lc-" + frappe.generate_hash(length=10) + "@example.test"
    return frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": "LC Test",
            "send_welcome_email": 0,
            "roles": [{"role": role}],
        }
    ).insert()


def create_shop():
    company = create_company()
    return frappe.get_doc(
        {"doctype": "LC Shop", "shop_name": company.name, "company": company.name}
    ).insert()


def add_member(shop, user, role="Owner"):
    return frappe.get_doc(
        {
            "doctype": "LC Shop Member",
            "shop": shop.name,
            "user": user.name,
            "membership_role": role,
            "enabled": 1,
        }
    ).insert()
