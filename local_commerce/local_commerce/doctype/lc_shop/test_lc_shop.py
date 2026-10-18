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

    def test_only_platform_admin_can_change_shop_location(self):
        frappe.set_user(self.owner.name)
        with self.assertRaises(frappe.PermissionError):
            update_shop(
                self.a.name,
                self.a.shop_name,
                self.a.status,
                address_line1="Owner supplied address",
                city="Test City",
                postal_code="403001",
                latitude=15.49,
                longitude=73.83,
                service_radius_km=5,
                live_tracking_enabled=1,
            )

        frappe.set_user("Administrator")
        result = update_shop(
            self.a.name,
            self.a.shop_name,
            self.a.status,
            address_line1="Admin supplied address",
            city="Test City",
            postal_code="403001",
            latitude=15.49,
            longitude=73.83,
            service_radius_km=5,
            live_tracking_enabled=1,
        )
        self.assertEqual(result["address_line1"], "Admin supplied address")

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

    def test_shops_can_share_a_company_without_sharing_access(self):
        second = frappe.get_doc(dict(doctype='LC Shop', shop_name='Another brand',
                                     company=self.a.company)).insert()
        frappe.set_user(self.owner.name)
        with self.assertRaises(frappe.PermissionError):
            get_shop(second.name)
        self.assertEqual([row.name for row in list_shops()], [self.a.name])


class TestShopCompanySelection(FrappeTestCase):
    def setUp(self):
        frappe.set_user('Administrator')
        self.original_platform = frappe.db.get_single_value('LC Store Settings', 'gst_company')

    def tearDown(self):
        frappe.set_user('Administrator')
        frappe.db.rollback()

    def test_missing_company_never_creates_legal_entity(self):
        from local_commerce.services.admin import create_shop as create
        name = 'Brand ' + frappe.generate_hash(length=10)
        frappe.db.set_single_value('LC Store Settings','gst_company','')
        with self.assertRaises(frappe.ValidationError):
            create(name)
        self.assertFalse(frappe.db.exists('Company', name))

    def test_existing_company_reused_for_two_owned_brands(self):
        from local_commerce.services.admin import create_shop as create
        from local_commerce.tests.helpers import create_company
        company = create_company()
        frappe.db.set_single_value('LC Store Settings','gst_company',company.name)
        first = create('Owned first', company=company.name)
        second = create('Owned second', company=company.name)
        self.assertEqual(first['company'], second['company'])
        self.assertNotEqual(first['name'], second['name'])
        self.assertEqual(frappe.db.get_value('LC Shop',first['name'],'business_model'), 'Owned shop')

    def test_existing_company_ignores_inherited_price_list(self):
        from local_commerce.tests.helpers import create_company
        company = create_company()
        shop = frappe.get_doc(dict(doctype='LC Shop', shop_name='Brand', company=company.name,
                                   selling_price_list='Standard Selling')).insert()
        self.assertFalse(shop.selling_price_list)

    def test_owner_cannot_change_warehouse_to_another_shop(self):
        from local_commerce.services.owner import configure
        from local_commerce.tests.helpers import create_company
        company = create_company()
        first = frappe.get_doc(dict(doctype='LC Shop',shop_name='First',company=company.name)).insert()
        second = frappe.get_doc(dict(doctype='LC Shop',shop_name='Second',company=company.name)).insert()
        owner = create_user('LC Shop Owner')
        add_member(first, owner)
        warehouse = frappe.get_doc(dict(doctype='Warehouse', warehouse_name='Shared test '+frappe.generate_hash(length=8),
                                        company=company.name, is_group=0)).insert()
        second.warehouse = warehouse.name
        second.save()
        frappe.set_user(owner.name)
        with self.assertRaises(frappe.PermissionError):
            configure(first.name, warehouse.name, None, None)

    def test_vendor_creation_creates_separate_company_transactionally(self):
        from local_commerce.services.admin import create_shop as create
        from local_commerce.tests.helpers import create_company
        platform = create_company()
        frappe.db.set_single_value('LC Store Settings','gst_company',platform.name)
        legal = 'LC Vendor Legal ' + frappe.generate_hash(length=8)
        result = create('Vendor brand', business_model='Third-party vendor',
                        platform_company=platform.name, company_name=legal,
                        country='India', currency='INR', gst_registration='Unregistered')
        self.assertEqual(result['company'],legal)
        self.assertNotEqual(result['company'],platform.name)
        self.assertTrue(frappe.db.exists('Account',{'company':legal}))
        with self.assertRaises(frappe.ValidationError):
            create('Another vendor',business_model='Third-party vendor',company=platform.name)
        with self.assertRaises(frappe.ValidationError):
            create('Duplicate vendor',business_model='Third-party vendor',company=legal)
