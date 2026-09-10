"""Account resolution with real ERPNext Customer/Portal User records."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services import customers, orders
from local_commerce.tests.helpers import create_user


class TestCustomerAccounts(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.user = create_user("LC Customer")
        self.other = create_user("LC Customer")
        settings = frappe.get_single("Selling Settings")
        if not settings.customer_group:
            settings.customer_group = frappe.get_all(
                "Customer Group", filters={"is_group": 0}, pluck="name", limit_page_length=1
            )[0]
        if not settings.territory:
            settings.territory = frappe.get_all("Territory", pluck="name", limit_page_length=1)[0]
        settings.save()
        self.group, self.territory = settings.customer_group, settings.territory

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def existing(self, email):
        return frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": "Existing " + frappe.generate_hash(length=8),
                "customer_type": "Individual",
                "customer_group": self.group,
                "territory": self.territory,
                "email_id": email,
            }
        ).insert()

    def save_address(self, label="Home", latitude=15.4909, longitude=73.8278, **values):
        return customers.save_address(
            values.get("name"),
            values.get("address_type", label if label in {"Home", "Work"} else "Other"),
            label,
            "LC Customer",
            "1234567890",
            f"{label} street",
            "Panaji",
            "403001",
            latitude,
            longitude,
            values.get("is_default", False),
        )

    def test_verified_account_reuses_existing_customer_and_portal_link(self):
        customer = self.existing(self.user.email)
        frappe.set_user(self.user.name)
        count = frappe.db.count("Customer")
        result = customers.ensure_customer()
        self.assertEqual(result["name"], customer.name)
        self.assertEqual(customers.ensure_customer(), result)
        self.assertEqual(frappe.db.count("Customer"), count)
        customer.reload()
        self.assertEqual([r.user for r in customer.portal_users], [self.user.name])

    def test_new_person_created_once_across_shops(self):
        frappe.set_user(self.user.name)
        count = frappe.db.count("Customer")
        first = orders.customer_record(self.user.name, "Company A")
        second = orders.customer_record(self.user.name, "Company B")
        self.assertEqual(first, second)
        self.assertEqual(frappe.db.count("Customer"), count + 1)

    def test_ambiguous_email_does_not_create_duplicate(self):
        self.existing(self.user.email)
        self.existing(self.user.email)
        count = frappe.db.count("Customer")
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.ValidationError):
            customers.ensure_customer()
        self.assertEqual(frappe.db.count("Customer"), count)
        self.assertFalse(frappe.db.exists("LC Customer Account", self.user.name))

    def test_guest_cannot_link_or_order(self):
        frappe.set_user("Guest")
        self.assertIsInstance(orders.shops(), list)
        with self.assertRaises(frappe.AuthenticationError):
            customers.ensure_customer()
        with self.assertRaises(frappe.AuthenticationError):
            orders.place("any", [], {}, "guest-request-key")

    def test_link_cannot_be_changed_via_resource_save(self):
        frappe.set_user(self.user.name)
        customers.ensure_customer()
        link = frappe.get_doc("LC Customer Account", self.user.name)
        link.user = self.other.name
        with self.assertRaises(frappe.PermissionError):
            link.save(ignore_permissions=True)

    def test_disabled_email_match_is_not_duplicated(self):
        customer = self.existing(self.user.email)
        customer.disabled = 1
        customer.save()
        count = frappe.db.count("Customer")
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.ValidationError):
            customers.ensure_customer()
        self.assertEqual(frappe.db.count("Customer"), count)

    def test_new_customer_uses_individual_without_selling_defaults(self):
        from unittest.mock import patch

        original = frappe.db.get_single_value

        def missing_defaults(doctype, field, *args, **kwargs):
            if doctype == "Selling Settings" and field in {"customer_group", "territory"}:
                return None
            return original(doctype, field, *args, **kwargs)

        frappe.set_user(self.user.name)
        with patch.object(frappe.db, "get_single_value", side_effect=missing_defaults):
            result = customers.ensure_customer()
        customer = frappe.get_doc("Customer", result["name"])
        self.assertEqual(customer.customer_group, "Individual")
        self.assertEqual(customer.customer_type, "Individual")
        self.assertTrue(frappe.db.exists("Territory", customer.territory))
        self.assertFalse(frappe.db.get_value("Customer Group", "Individual", "is_group"))

    def test_saved_addresses_have_one_default_and_can_be_archived(self):
        frappe.set_user(self.user.name)
        home = self.save_address()
        self.assertTrue(home["is_default"])
        work = self.save_address("Work", is_default=True)
        listed = customers.list_addresses()
        self.assertEqual([row["name"] for row in listed], [work["name"], home["name"]])
        self.assertFalse(next(row for row in listed if row["name"] == home["name"])["is_default"])
        customers.archive_address(work["name"])
        remaining = customers.list_addresses()
        self.assertEqual(len(remaining), 1)
        self.assertTrue(remaining[0]["is_default"])

    def test_customer_cannot_change_another_users_saved_address(self):
        frappe.set_user(self.user.name)
        address = self.save_address()
        frappe.set_user(self.other.name)
        with self.assertRaises(frappe.PermissionError):
            self.save_address("Stolen", name=address["name"])
        with self.assertRaises(frappe.PermissionError):
            customers.archive_address(address["name"])

    def test_raw_saved_address_edit_is_denied(self):
        frappe.set_user(self.user.name)
        address = self.save_address()
        doc = frappe.get_doc("LC Customer Address", address["name"])
        doc.city = "Changed outside service"
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)
