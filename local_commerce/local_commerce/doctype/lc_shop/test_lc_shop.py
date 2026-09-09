import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.api.shops import get_shop, list_shops, update_shop
from local_commerce.tests.helpers import add_member, create_shop, create_user


class TestLCShop(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.a, self.b = create_shop(), create_shop()
        self.owner = create_user("LC Shop Owner")
        self.member = add_member(self.a, self.owner)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_cross_shop_api_and_document_denied(self):
        frappe.set_user(self.owner.name)
        self.assertEqual([s.name for s in list_shops()], [self.a.name])
        self.assertEqual(get_shop(self.a.name)["company"], self.a.company)
        with self.assertRaises(frappe.PermissionError):
            get_shop(self.b.name)
        with self.assertRaises(frappe.PermissionError):
            self.b.check_permission("read")
        with self.assertRaises(frappe.PermissionError):
            update_shop(self.b.name, "Changed", "Active")

    def test_owner_cannot_change_company_through_resource_save(self):
        frappe.set_user(self.owner.name)
        self.a.company = self.b.company
        with self.assertRaises(frappe.PermissionError):
            self.a.save()

    def test_revocation_applies_immediately(self):
        self.member.enabled = 0
        self.member.save()
        frappe.set_user(self.owner.name)
        with self.assertRaises(frappe.PermissionError):
            get_shop(self.a.name)
        self.assertEqual(list_shops(), [])

    def test_owner_settings_and_version_audit(self):
        frappe.set_user(self.owner.name)
        result = update_shop(self.a.name, "Updated shop", "Temporarily Closed")
        self.assertEqual(result["status"], "Temporarily Closed")
        self.assertTrue(
            frappe.db.exists("Version", {"ref_doctype": "LC Shop", "docname": self.a.name})
        )

    def test_company_is_unique(self):
        with self.assertRaises(frappe.UniqueValidationError):
            frappe.get_doc(
                {"doctype": "LC Shop", "shop_name": "Duplicate", "company": self.a.company}
            ).insert()


class TestShopCompanyCreation(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def new_shop(self):
        return frappe.get_doc(
            {
                "doctype": "LC Shop",
                "shop_name": "LC Auto " + frappe.generate_hash(length=10),
                "company_country": "United States",
                "company_currency": "USD",
            }
        )

    def test_platform_creates_company_without_company_role(self):
        user = create_user("LC Platform Administrator")
        frappe.set_user(user.name)
        shop = self.new_shop()
        shop.selling_price_list = "Standard Selling"
        shop.insert()
        self.assertFalse(shop.selling_price_list)
        self.assertEqual(shop.company, shop.shop_name)
        company = frappe.get_doc("Company", shop.company)
        self.assertEqual(company.country, "United States")
        self.assertEqual(company.default_currency, "USD")
        self.assertTrue(frappe.db.exists("Account", {"company": company.name}))
        self.assertTrue(frappe.db.exists("Warehouse", {"company": company.name}))
        original = shop.company
        shop.shop_name = "Changed display name"
        shop.save()
        self.assertEqual(shop.company, original)

    def test_existing_name_requires_explicit_link(self):
        first = self.new_shop().insert()
        duplicate = self.new_shop()
        duplicate.shop_name = first.shop_name
        with self.assertRaises(frappe.ValidationError):
            duplicate.insert()

    def test_owner_cannot_trigger_company_creation_even_with_permission_bypass(self):
        owner = create_user("LC Shop Owner")
        shop = self.new_shop()
        frappe.set_user(owner.name)
        with self.assertRaises(frappe.PermissionError):
            shop.insert(ignore_permissions=True)
        self.assertFalse(frappe.db.exists("Company", shop.shop_name))

    def test_site_defaults_are_used(self):
        from unittest.mock import patch

        shop = self.new_shop()
        shop.company_country = shop.company_currency = None
        original = frappe.db.get_single_value

        def defaults(doctype, field, *args, **kwargs):
            if doctype == "Global Defaults" and field in {"country", "default_currency"}:
                return {"country": "United States", "default_currency": "USD"}[field]
            return original(doctype, field, *args, **kwargs)

        with patch.object(frappe.db, "get_single_value", side_effect=defaults):
            shop.insert()
        self.assertEqual(shop.company, shop.shop_name)

    def test_existing_company_ignores_inherited_price_list(self):
        from local_commerce.tests.helpers import create_company

        company = create_company()
        shop = self.new_shop()
        shop.company = company.name
        shop.selling_price_list = "Standard Selling"
        shop.insert()
        self.assertFalse(shop.selling_price_list)
        self.assertFalse(frappe.db.get_value("LC Shop", shop.name, "selling_price_list"))
