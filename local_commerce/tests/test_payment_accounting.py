"""Run on a disposable ERPNext v15 site; provider HTTP is stubbed, native GL is not."""

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from local_commerce.services import orders
from local_commerce.services.payments import accounting, cashfree
from local_commerce.tests.test_manual_upi import TestManualUpi


class TestPaymentAccounting(FrappeTestCase):
    def setUp(self):
        TestManualUpi.setUp(self)
        frappe.set_user("Administrator")
        self.gateway = frappe.get_doc(
            dict(
                doctype="LC Payment Gateway",
                name="Accounting test " + frappe.generate_hash(length=8),
                enabled=1,
                environment="sandbox",
                client_id="test-client",
                client_secret="test-secret",
            )
        ).insert()
        self.real_bank = frappe.copy_doc(self.bank)
        self.real_bank.account_name = "Settlement " + frappe.generate_hash(length=8)
        self.real_bank.insert()
        self.expense = frappe.db.get_value(
            "Account",
            {"company": self.shop.company, "root_type": "Expense", "is_group": 0, "disabled": 0},
            "name",
        )
        self.shop.reload()
        self.shop.update(
            dict(
                cashfree_enabled=1,
                cashfree_gateway=self.gateway.name,
                cashfree_settlement_mode="Direct merchant",
                cashfree_clearing_account=self.bank.name,
                cashfree_mode_of_payment=self.mode.name,
                cashfree_bank_account=self.real_bank.name,
                cashfree_fee_account=self.expense,
                cashfree_fee_tax_account=self.expense,
            )
        )
        self.shop.save()
        frappe.set_user(self.customer.name)
        order = orders.place(
            self.shop.name,
            [{"item": self.item, "quantity": 1}],
            self.address,
            "accounting-test",
            "Cashfree",
        )
        self.order = frappe.get_doc("LC Order", order["name"])
        self.order.gateway_payment_id = "test-payment"
        self.order.payment_status = "Paid"
        cashfree.book_payment(self.order)
        cashfree.save(self.order)
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_full_refund_offsets_receivable_and_clearing_without_stock_return(self):
        total = json.loads(self.order.gateway_snapshot)["amount"]
        row = dict(
            cf_refund_id="test-refund",
            cf_payment_id="test-payment",
            order_id=self.order.gateway_order_id,
            refund_amount=total,
            refund_currency="INR",
            refund_status="SUCCESS",
        )
        self.order.gateway_refunded_amount = float(total)
        accounting.book_refunds(self.order, [row])
        accounting.book_refunds(self.order, [row])
        record = accounting.state(self.order)["refunds"]["test-refund"]
        credit = frappe.get_doc("Sales Invoice", record["credit_note"])
        payment = frappe.get_doc("Payment Entry", record["payment_entry"])
        self.assertEqual(credit.docstatus, 1)
        self.assertEqual(credit.update_stock, 0)
        self.assertEqual(credit.outstanding_amount, 0)
        self.assertEqual(payment.payment_type, "Pay")
        self.assertEqual(payment.paid_amount, float(total))
        gl = frappe.db.sql(
            """select sum(debit-credit) from `tabGL Entry`
            where company=%s and account=%s and is_cancelled=0""",
            (self.shop.company, self.bank.name),
        )[0][0]
        self.assertAlmostEqual(float(gl or 0), 0, places=2)
        self.assertEqual(
            frappe.db.count(
                "Sales Invoice", {"return_against": self.order.sales_invoice, "docstatus": 1}
            ),
            1,
        )

    def test_settlement_transfers_only_net_and_books_fees_once(self):
        total = float(json.loads(self.order.gateway_snapshot)["amount"])
        payload = dict(
            order_details=dict(
                order_id=self.order.gateway_order_id, order_amount=total, order_currency="INR"
            ),
            payment_details=dict(
                cf_payment_id="test-payment",
                payment_amount=total,
                payment_currency="INR",
                charge_type="PREPAID",
                charged_to="MERCHANT",
                pg_service_charge=1,
                pg_service_tax=0.18,
                split_service_charge=0,
                split_service_tax=0,
                settlement_amount=total - 1.18,
            ),
            settlement_details=dict(
                status="SUCCESS",
                settlement_currency="INR",
                cf_settlement_id="test-settlement",
                settlement_utr="test-utr",
                settlement_processed_on=str(frappe.utils.now_datetime()),
            ),
        )
        # Mutex helper normally commits its read-only preflight. Keep test fixtures transactional.
        with (
            patch.object(cashfree, "begin_operation"),
            patch.object(cashfree, "request", return_value=payload),
        ):
            first = accounting.reconcile_settlement(self.order.name)
            second = accounting.reconcile_settlement(self.order.name)
        self.assertEqual(first["journal_entry"], second["journal_entry"])
        journal = frappe.get_doc("Journal Entry", first["journal_entry"])
        self.assertEqual(journal.docstatus, 1)
        self.assertAlmostEqual(journal.total_debit, total, places=2)
        self.assertAlmostEqual(journal.total_credit, total, places=2)
        net = next(
            r.debit_in_account_currency
            for r in journal.accounts
            if r.account == self.real_bank.name
        )
        self.assertAlmostEqual(net, total - 1.18, places=2)
