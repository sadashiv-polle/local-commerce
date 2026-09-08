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
