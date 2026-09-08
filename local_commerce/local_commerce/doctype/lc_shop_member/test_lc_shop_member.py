import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.tests.helpers import add_member, create_shop, create_user


class TestLCShopMember(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.shop = create_shop()
        self.user = create_user("LC Shop Owner")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_duplicate_membership_rejected(self):
        add_member(self.shop, self.user)
        with self.assertRaises(frappe.ValidationError):
            add_member(self.shop, self.user)

    def test_membership_does_not_grant_roles(self):
        user = create_user("LC Customer")
        with self.assertRaises(frappe.ValidationError):
            add_member(self.shop, user)

    def test_owner_cannot_grant_membership(self):
        add_member(self.shop, self.user)
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.PermissionError):
            add_member(self.shop, self.user)

    def test_index_hook_is_idempotent(self):
        from local_commerce.install import after_migrate

        after_migrate()
        after_migrate()
