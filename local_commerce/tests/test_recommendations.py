"""Identity boundaries; run on a disposable ERPNext v15 site."""

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services.recommendations import suggestions
from local_commerce.tests.helpers import create_user


class TestRecommendations(FrappeTestCase):
    def test_guest_gets_no_purchase_history(self):
        frappe.set_user("Guest")
        try:
            self.assertEqual(suggestions()["items"], [])
        finally:
            frappe.set_user("Administrator")

    def test_new_account_gets_no_other_customers_purchases(self):
        user = create_user("LC Customer")
        frappe.set_user(user.name)
        try:
            self.assertEqual(suggestions()["items"], [])
            with self.assertRaises(frappe.PermissionError):
                suggestions("address-that-is-not-owned-by-this-user")
        finally:
            frappe.set_user("Administrator")
