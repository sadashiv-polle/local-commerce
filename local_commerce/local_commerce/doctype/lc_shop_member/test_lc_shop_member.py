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
        member = add_member(self.shop, self.user)
        self.assertEqual(member.shop_name, self.shop.shop_name)
        with self.assertRaises(frappe.ValidationError):
            add_member(self.shop, self.user)

    def test_membership_assigns_matching_role(self):
        user = create_user("LC Customer")
        member = add_member(self.shop, user, "Delivery Person")
        self.assertEqual(member.membership_role, "Delivery Person")
        self.assertIn("LC Delivery Person", frappe.get_roles(user.name))
        self.assertEqual(
            frappe.db.count(
                "Has Role", {"parent": user.name, "role": "LC Delivery Person"}
            ),
            1,
        )

    def test_membership_title_follows_shop_name(self):
        member = add_member(self.shop, self.user)
        self.shop.shop_name = "Readable shop title"
        self.shop.save()
        member.reload()
        self.assertEqual(member.shop_name, "Readable shop title")

    def test_owner_cannot_grant_membership(self):
        add_member(self.shop, self.user)
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.PermissionError):
            add_member(self.shop, self.user)

    def test_index_hook_is_idempotent(self):
        from local_commerce.install import after_migrate

        after_migrate()
        after_migrate()
