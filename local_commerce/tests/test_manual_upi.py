"""Run on a disposable ERPNext site: verifies bank GL and delivery without cash."""

import io
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from PIL import Image

from local_commerce.services import manual_upi, orders
from local_commerce.tests.helpers import add_member, create_user
from local_commerce.tests.test_orders import TestDeliveryOrders


class TestManualUpi(FrappeTestCase):
    def setUp(self):
        def inr_company():
            suffix = frappe.generate_hash(length=8)
            return frappe.get_doc(
                {
                    "doctype": "Company",
                    "company_name": "UPI Test " + suffix,
                    "abbr": suffix,
                    "default_currency": "INR",
                    "country": "India",
                }
            ).insert()

        with patch("local_commerce.tests.helpers.create_company", side_effect=inr_company):
            TestDeliveryOrders.setUp(self)
        frappe.set_user("Administrator")
        parent = frappe.db.get_value(
            "Account",
            {
                "company": self.shop.company,
                "account_type": "Bank",
                "is_group": 1,
            },
            "name",
        )
        self.assertTrue(parent, "Test Company needs the Bank Accounts group")
        self.bank = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": "UPI Test " + frappe.generate_hash(length=8),
                "company": self.shop.company,
                "parent_account": parent,
                "account_type": "Bank",
                "account_currency": "INR",
                "is_group": 0,
            }
        ).insert()
        self.mode = frappe.get_doc(
            {
                "doctype": "Mode of Payment",
                "mode_of_payment": "UPI " + frappe.generate_hash(length=8),
                "type": "Bank",
                "enabled": 1,
            }
        ).insert()
        manual_upi.configure(
            self.shop.name, 1, "fishworld@testbank", self.bank.name, self.mode.name
        )
        orders.configure_cod(self.shop.name, 0)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_upi_only_checkout_verification_bank_entry_and_delivery(self):
        frappe.set_user(self.customer.name)
        self.assertEqual(orders.catalog(self.shop.name)["payment_methods"], ["Manual UPI"])
        order = orders.place(
            self.shop.name,
            [{"item": self.item, "quantity": 1}],
            self.address,
            "manual-upi-test-order",
            "Manual UPI",
        )
        name = order["name"]
        self.assertFalse(order["upi"]["payable"])
        frappe.set_user(self.user.name)
        orders.change(name, "Accepted")
        orders.change(name, "Preparing")
        orders.change(name, "Ready")
        frappe.set_user("Administrator")
        rider = create_user("LC Delivery Person")
        add_member(self.shop, rider, "Delivery Person")
        frappe.set_user(self.user.name)
        orders.assign_driver(name, rider.name)
        frappe.set_user(rider.name)
        with self.assertRaises(frappe.ValidationError):
            orders.delivery_change(name, "Picked Up")
        frappe.set_user(self.customer.name)
        content = io.BytesIO()
        Image.new("RGB", (10, 10), "green").save(content, "PNG")
        content.seek(0)
        with patch.object(
            frappe.local, "request", SimpleNamespace(files={"file": content}), create=True
        ):
            proof = manual_upi.upload_proof(name)
        self.assertEqual(proof["payment_status"], "Awaiting Verification")
        self.assertTrue(proof["upi"]["proof"].startswith("/private/files/"))
        frappe.set_user(self.user.name)
        paid = manual_upi.review(name, 1, "TEST123456789")
        self.assertEqual(paid["payment_status"], "Paid")
        invoice = frappe.get_doc("Sales Invoice", paid["sales_invoice"])
        payment = frappe.get_doc("Payment Entry", paid["payment_entry"])
        self.assertEqual(invoice.docstatus, 1)
        self.assertEqual(invoice.outstanding_amount, 0)
        self.assertEqual(payment.docstatus, 1)
        self.assertEqual(payment.paid_to, self.bank.name)
        self.assertEqual(manual_upi.review(name, 1, "TEST123456789")["payment_entry"], payment.name)
        with self.assertRaises(frappe.ValidationError):
            orders.change(name, "Cancelled", "Cancel paid order")
        frappe.set_user(rider.name)
        self.assertIsNone(orders.detail(name)["upi"])
        orders.delivery_change(name, "Picked Up")
        orders.delivery_change(name, "Out for Delivery")
        frappe.set_user(self.customer.name)
        otp = orders.detail(name)["delivery_otp"]
        frappe.set_user(rider.name)
        delivered = orders.delivery_change(name, "Delivered", delivery_otp_value=otp)
        self.assertEqual(delivered["payment_status"], "Paid")
        self.assertEqual(delivered["sales_invoice"], invoice.name)
        self.assertFalse(frappe.db.exists("LC COD Collection", {"order": name}))
