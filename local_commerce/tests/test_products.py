import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.api.products import create_item, list_items, options
from local_commerce.services.products import item_permission, validate_item
from local_commerce.tests.helpers import add_member, create_shop, create_user


class TestProducts(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.a, self.b = create_shop(), create_shop()
        self.owner = create_user("LC Shop Owner")
        self.member = add_member(self.a, self.owner)
        self.group = frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name")[0]
        self.uom = frappe.get_all("UOM", filters={"enabled": 1}, pluck="name")[0]

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def create(self, shop):
        return create_item(shop, "Test product", self.group, self.uom)

    def test_owner_creates_item_with_authoritative_company(self):
        frappe.set_user(self.owner.name)
        result = self.create(self.a.name)
        item = frappe.get_doc("Item", result["name"])
        self.assertEqual(item.lc_shop, self.a.name)
        self.assertEqual(item.item_defaults[0].company, self.a.company)
        self.assertEqual(item.owner, self.owner.name)
        self.assertEqual([i.name for i in list_items(self.a.name)], [item.name])

    def test_cross_shop_operations_denied(self):
        other = self.create(self.b.name)
        self.owner.add_roles("Stock Manager")
        frappe.set_user(self.owner.name)
        for operation in (self.create, list_items, options):
            with self.assertRaises(frappe.PermissionError):
                operation(self.b.name)
        self.assertFalse(
            item_permission(frappe.get_doc("Item", other["name"]), permission_type="read")
        )
        self.assertEqual(frappe.get_list("Item", filters={"name": other["name"]}), [])
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc("Item", other["name"]).check_permission("read")

    def test_staff_cannot_create(self):
        staff = create_user("LC Shop Staff")
        add_member(self.a, staff, "Staff")
        frappe.set_user(staff.name)
        with self.assertRaises(frappe.PermissionError):
            self.create(self.a.name)
        self.assertEqual(list_items(self.a.name), [])

    def test_revoked_owner_cannot_create(self):
        self.member.enabled = 0
        self.member.save()
        frappe.set_user(self.owner.name)
        with self.assertRaises(frappe.PermissionError):
            self.create(self.a.name)

    def test_item_ownership_is_immutable(self):
        item = frappe.get_doc("Item", self.create(self.a.name)["name"])
        item.lc_shop = self.b.name
        with self.assertRaises(frappe.PermissionError):
            item.save()

    def test_owner_cannot_use_direct_item_insert(self):
        frappe.set_user(self.owner.name)
        doc = frappe.get_doc({"doctype": "Item", "item_code": "forged", "lc_shop": self.b.name})
        with self.assertRaises(frappe.PermissionError):
            validate_item(doc)

    def test_invalid_taxonomy_creates_nothing(self):
        frappe.set_user(self.owner.name)
        with self.assertRaises(frappe.ValidationError):
            create_item(self.a.name, "Test", "nonexistent-category", self.uom)
        self.assertEqual(list_items(self.a.name), [])
