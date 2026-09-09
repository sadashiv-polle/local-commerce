from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services import registration


class TestRegistration(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_email_failure_does_not_create_user(self):
        email = "registration-" + frappe.generate_hash(length=10) + "@example.test"
        with (
            patch.object(registration, "signup_allowed"),
            patch.object(frappe, "sendmail", side_effect=RuntimeError("SMTP unavailable")),
        ):
            with self.assertRaises(frappe.ValidationError):
                registration.begin(email, "Test User", "/local-commerce#/store")
        self.assertFalse(frappe.db.exists("User", email))

    def test_code_must_match_before_creating_user(self):
        email = "registration-" + frappe.generate_hash(length=10) + "@example.test"
        with (
            patch.object(registration, "signup_allowed"),
            patch.object(frappe, "sendmail"),
            patch.object(registration.secrets, "randbelow", return_value=123456),
        ):
            result = registration.begin(email, "Test User", "/local-commerce#/store")
            try:
                for _ in range(5):
                    with self.assertRaises(frappe.ValidationError):
                        registration.complete(
                            result["challenge_id"], "000000", "Valid-test-pass-123!"
                        )
                with self.assertRaises(frappe.ValidationError):
                    registration.complete(result["challenge_id"], "123456", "Valid-test-pass-123!")
                self.assertFalse(frappe.db.exists("User", email))
            finally:
                frappe.cache.delete_value("lc-signup:" + result["challenge_id"])
