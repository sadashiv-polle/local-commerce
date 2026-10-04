import ast
import copy
import importlib.util
import json
import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from local_commerce.services.payments.reconciliation_rules import (
    refunds_for_order,
    settlement_evidence,
)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.snap = dict(amount="350", currency="INR", settlement_mode="Direct merchant")
        self.payload = dict(
            order_details=dict(order_id="order", order_amount=350, order_currency="INR"),
            payment_details=dict(
                cf_payment_id="42",
                payment_amount=350,
                payment_currency="INR",
                charge_type="PREPAID",
                charged_to="MERCHANT",
                pg_service_charge=7,
                pg_service_tax=1.26,
                split_service_charge=0,
                split_service_tax=0,
                settlement_amount=341.74,
            ),
            settlement_details=dict(
                status="SUCCESS",
                settlement_currency="INR",
                cf_settlement_id=88,
                settlement_utr="UTR",
                settlement_processed_on="2026-10-04T12:00:00+05:30",
            ),
        )

    def evidence(self):
        return settlement_evidence(self.payload, self.snap, "order", "42")

    def test_settlement_net_plus_fees_and_tax_equals_gross(self):
        result = self.evidence()
        self.assertEqual(result["net"], "341.74")
        self.assertEqual(result["fee"], "7.00")
        self.assertEqual(result["tax"], "1.26")

    def test_pending_is_not_bank_credit(self):
        self.payload["settlement_details"]["status"] = "PENDING"
        self.assertIsNone(self.evidence())

    def test_bad_identity_currency_or_unexplained_adjustments_fail_closed(self):
        for section, key, value in [
            ("order_details", "order_id", "other"),
            ("payment_details", "cf_payment_id", "other"),
            ("payment_details", "payment_amount", 349),
            ("settlement_details", "settlement_currency", "USD"),
            ("settlement_details", "settlement_utr", None),
            ("payment_details", "settlement_amount", 350),
            ("payment_details", "charge_type", "POSTPAID"),
        ]:
            payload = copy.deepcopy(self.payload)
            payload[section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                settlement_evidence(payload, self.snap, "order", "42")

    def test_vendor_does_not_receive_platform_commission_or_other_vendor_amount(self):
        snap = dict(self.snap, settlement_mode="Easy Split", vendor_id="vendor", vendor_amount=330)
        row = dict(
            merchant_order_id="order",
            merchant_vendor_id="vendor",
            entity_type="vendor_commission",
            sale_type="CREDIT",
            settled="YES",
            currency="INR",
            amount=330,
            vendor_pg_service_charge=2,
            vendor_pg_service_tax=0.36,
            vendor_split_service_charges=0,
            vendor_split_service_tax=0,
            vendor_settlement_id="88",
            vendor_settlement_utr="UTR",
            vendor_settlement_time="2026-10-04 12:00:00",
        )
        payload = {"data": [dict(row, merchant_vendor_id="other"), row], "cursor": None}
        result = settlement_evidence(payload, snap, "order", "42")
        self.assertEqual(result["gross"], "330.00")
        self.assertEqual(result["net"], "327.64")
        payload["cursor"] = "more"
        with self.assertRaises(ValueError):
            settlement_evidence(payload, snap, "order", "42")

    def test_refunds_deduplicate_and_reject_wrong_payment_and_over_refunds(self):
        row = dict(
            cf_refund_id="R1",
            cf_payment_id=42,
            order_id="order",
            refund_currency="INR",
            refund_amount=350,
            refund_status="SUCCESS",
        )
        self.assertEqual(len(refunds_for_order([row, row], "order", "42", "INR", 350)), 1)
        for change in [
            dict(refund_amount=351),
            dict(cf_payment_id=43),
            dict(refund_currency="USD"),
            dict(cf_refund_id=""),
            dict(refund_amount=0),
        ]:
            with self.assertRaises(ValueError):
                refunds_for_order([{**row, **change}], "order", "42", "INR", 350)


class Doc(SimpleNamespace):
    def get(self, name, default=None):
        return getattr(self, name, default)


class PostingTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        owner = Mock(reject=Mock(side_effect=ValueError))
        self.modules = patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "local_commerce.services.owner": owner,
                "local_commerce.permissions.scope": Mock(),
            },
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location(
            "local_commerce.services.payments.accounting",
            Path("local_commerce/services/payments/accounting.py"),
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.posting = nullcontext
        self.module.account = Mock()
        self.module.submitted = Mock()
        self.module.persist = lambda doc, data: setattr(
            doc, "gateway_accounting_json", json.dumps(data)
        )
        self.doc = Doc(
            name="order",
            gateway_order_id="order",
            gateway_profile="profile",
            gateway_payment_id="42",
            sales_invoice="SI",
            payment_entry="PE",
            shop="shop",
            gateway_refunded_amount=350,
            gateway_accounting_json="",
            gateway_snapshot=json.dumps(
                dict(
                    amount="350",
                    currency="INR",
                    clearing_account="Clearing",
                    mode_of_payment="Cashfree",
                    commission="0",
                )
            ),
        )
        self.invoice = Doc(
            name="SI", company="C", customer="customer", currency="INR", grand_total=350
        )
        self.credit = Doc(
            name="CN",
            docstatus=1,
            is_return=1,
            return_against="SI",
            company="C",
            customer="customer",
            currency="INR",
            update_outstanding_for_self=1,
            grand_total=-350,
            outstanding_amount=-350,
            submit=Mock(),
            reload=Mock(),
        )
        self.credit.insert = Mock(return_value=self.credit)
        self.payment = Doc(name="REFUND-PE", payment_type="Pay", paid_amount=350, submit=Mock())
        self.payment.insert = Mock(return_value=self.payment)
        self.pe_module = Mock(get_payment_entry=Mock(return_value=self.payment))
        self.si_module = Mock(make_sales_return=Mock(return_value=self.credit))
        mocks = patch.dict(
            sys.modules,
            {
                "erpnext.accounts.doctype.payment_entry.payment_entry": self.pe_module,
                "erpnext.accounts.doctype.sales_invoice.sales_invoice": self.si_module,
            },
        )
        mocks.start()
        self.addCleanup(mocks.stop)
        self.frappe.get_doc.side_effect = lambda dt, name: (
            self.invoice if name == "SI" else self.credit
        )
        self.frappe.db.exists.return_value = False
        self.refund = dict(
            cf_refund_id="R1",
            order_id="order",
            refund_amount=350,
            refund_currency="INR",
            refund_status="SUCCESS",
            cf_payment_id=42,
        )

    def test_full_refund_posts_native_credit_and_outgoing_payment_once(self):
        self.module.book_refunds(self.doc, [self.refund])
        self.module.book_refunds(self.doc, [self.refund, self.refund])
        self.si_module.make_sales_return.assert_called_once_with("SI")
        self.payment.submit.assert_called_once()
        self.assertEqual(self.credit.update_stock, 0)
        self.assertEqual(self.credit.update_outstanding_for_self, 1)
        self.assertEqual(
            json.loads(self.doc.gateway_accounting_json)["refunds"]["R1"]["payment_entry"],
            "REFUND-PE",
        )

    def test_partial_refund_never_guesses_which_items_or_tax_to_credit(self):
        self.refund["refund_amount"] = self.doc.gateway_refunded_amount = 100
        with self.assertRaises(ValueError):
            self.module.book_refunds(self.doc, [self.refund])
        self.si_module.make_sales_return.assert_not_called()
        self.payment.submit.assert_not_called()

    def test_partial_refund_uses_matching_native_credit(self):
        self.refund["refund_amount"] = self.doc.gateway_refunded_amount = 100
        self.doc.gateway_accounting_json = json.dumps({"refund_credit_notes": {"R1": "CN"}})
        self.credit.grand_total = self.credit.outstanding_amount = -100
        self.payment.paid_amount = 100
        self.module.book_refunds(self.doc, [self.refund])
        self.si_module.make_sales_return.assert_not_called()
        self.payment.submit.assert_called_once()

    def test_existing_credit_or_wrong_customer_does_not_create_duplicate_refund(self):
        self.frappe.db.exists.return_value = True
        with self.assertRaises(ValueError):
            self.module.book_refunds(self.doc, [self.refund])
        self.doc.gateway_accounting_json = json.dumps({"refund_credit_notes": {"R1": "CN"}})
        self.credit.customer = "someone-else"
        with self.assertRaises(ValueError):
            self.module.book_refunds(self.doc, [self.refund])
        self.payment.submit.assert_not_called()

    def test_settlement_journal_balances_and_replay_reuses_it(self):
        import local_commerce.services.payments as package

        self.doc.gateway_snapshot = json.dumps(
            dict(
                amount="350",
                currency="INR",
                settlement_mode="Direct merchant",
                clearing_account="Clearing",
            )
        )
        payload = EvidenceTests()
        payload.setUp()
        provider = Mock()
        provider.payment_order.return_value = self.doc
        provider.locked.return_value = self.doc
        provider.request.return_value = payload.payload
        shop = Doc(
            company="C",
            cashfree_bank_account="Bank",
            cashfree_fee_account="Fees",
            cashfree_fee_tax_account="Fee Tax",
            cost_center="Main",
        )
        journal = Doc(name="JV", submit=Mock())
        journal.insert = Mock(return_value=journal)
        created = []

        def get_doc(dt, name=None):
            if isinstance(dt, dict):
                created.append(dt)
                return journal
            return shop

        self.frappe.get_doc.side_effect = get_doc
        self.frappe.db.get_value.return_value = "C"
        self.frappe.db.sql.return_value = []
        with patch.object(package, "cashfree", provider, create=True):
            result = self.module.reconcile_settlement("order")
            again = self.module.reconcile_settlement("order")
            self.assertEqual(result, again)
            self.assertEqual(len(created), 1)
            lines = created[0]["accounts"]
            debit = sum(r.get("debit_in_account_currency", 0) for r in lines)
            credit = sum(r.get("credit_in_account_currency", 0) for r in lines)
            self.assertEqual(debit, credit)
            self.assertEqual(credit, 350)
            self.assertEqual(lines[0]["account"], "Bank")
            self.assertEqual(lines[0]["debit_in_account_currency"], 341.74)
            self.module.submitted.side_effect = ValueError("cancelled journal")
            with self.assertRaises(ValueError):
                self.module.reconcile_settlement("order")
            self.assertEqual(len(created), 1)


class CODDifferenceTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path("local_commerce/services/orders.py").read_text())
        fn = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "reconcile_cod"
        )
        self.order = Doc(
            name="order",
            status="Delivered",
            payment_status="Collected",
            payment_entry=None,
            sales_invoice="SI",
            save=Mock(),
            add_comment=Mock(),
        )
        self.record = Doc(
            name="collection",
            shop="shop",
            order="order",
            variance=-10,
            status="Awaiting Handover",
            collected_amount=90,
            reload=Mock(),
            save=Mock(),
        )
        self.frappe = Mock()
        self.frappe.get_doc.side_effect = lambda dt, name: (
            self.order if dt == "LC Order" else self.record
        )
        self.outstanding, self.unallocated = 10, 0
        self.frappe.db.get_value.side_effect = lambda dt, name, field: (
            1
            if field == "docstatus"
            else self.outstanding
            if field == "outstanding_amount"
            else self.unallocated
        )
        self.create_payment = Mock(return_value="PE")
        scope = dict(
            frappe=self.frappe,
            require_shop=Mock(),
            reject=Mock(side_effect=ValueError),
            _order_operation=Mock(),
            now_datetime=Mock(),
            escape=lambda s: s,
            create_cod_payment=self.create_payment,
            serialize_collection=lambda r: r,
        )
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<cod>", "exec"), scope)
        self.reconcile = scope["reconcile_cod"]

    def test_shortage_stays_pending_and_retry_does_not_receive_cash_twice(self):
        self.reconcile("collection", "short cash")
        self.assertEqual(self.record.status, "Difference Pending")
        self.assertEqual(self.order.payment_status, "Partially Paid")
        self.reconcile("collection", "still short")
        self.create_payment.assert_called_once()
        self.outstanding = 0
        self.reconcile("collection", "settled by admin")
        self.assertEqual(self.record.status, "Reconciled")
        self.create_payment.assert_called_once()

    def test_excess_cash_remains_customer_credit(self):
        self.outstanding, self.unallocated = 0, 10
        self.reconcile("collection", "extra cash")
        self.assertEqual(self.order.payment_status, "Overpaid")
        self.assertEqual(self.record.status, "Difference Pending")


class HistoricalCODTests(unittest.TestCase):
    def test_migration_reopens_only_unsettled_cod_without_touching_books(self):
        import sqlite3

        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("""
            create table `tabLC Order` (name, payment_method, payment_status,
                sales_invoice, payment_entry);
            create table `tabSales Invoice` (name,docstatus,outstanding_amount);
            create table `tabPayment Entry` (name,docstatus,unallocated_amount);
            create table `tabLC COD Collection` (`order`, status);
            insert into `tabLC Order` values
                ('short','Cash on Delivery','Reconciled','I1','P1'),
                ('extra','Cash on Delivery','Reconciled','I2','P2'),
                ('paid','Cash on Delivery','Reconciled','I3','P3'),
                ('upi','Manual UPI','Reconciled','I1','P1');
            insert into `tabSales Invoice` values ('I1',1,10), ('I2',1,0), ('I3',1,0);
            insert into `tabPayment Entry` values ('P1',1,0), ('P2',1,10), ('P3',1,0);
            insert into `tabLC COD Collection` values
                ('short','Reconciled'), ('extra','Reconciled'), ('paid','Reconciled');
        """)
        tree = ast.parse(Path("local_commerce/install.py").read_text())
        fn = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "repair_cod_differences"
        )
        scope = dict(frappe=SimpleNamespace(db=SimpleNamespace(sql=db.execute)))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<migration>", "exec"), scope)
        scope["repair_cod_differences"]()
        scope["repair_cod_differences"]()
        self.assertEqual(
            dict(db.execute("select name,payment_status from `tabLC Order`")),
            {
                "short": "Partially Paid",
                "extra": "Overpaid",
                "paid": "Reconciled",
                "upi": "Reconciled",
            },
        )
        self.assertEqual(
            dict(db.execute("select * from `tabLC COD Collection`")),
            {"short": "Difference Pending", "extra": "Difference Pending", "paid": "Reconciled"},
        )
        self.assertEqual(
            db.execute(
                'select outstanding_amount from `tabSales Invoice` where name="I1"'
            ).fetchone()[0],
            10,
        )
