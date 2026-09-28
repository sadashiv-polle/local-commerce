"""Execute the migration SQL against receipts, including incomplete/unsafe cases."""

import ast
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace


class PaymentStatusMigrationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            create table `tabLC Order` (name text, payment_method text,
                payment_status text, payment_entry text, sales_invoice text,
                gateway_payment_id text, gateway_accounting_error text,
                gateway_refunded_amount real);
            create table `tabPayment Entry` (name text, docstatus integer,
                lc_order text, payment_type text);
            create table `tabSales Invoice` (name text, docstatus integer,
                lc_order text, is_return integer);
        """)
        tree = ast.parse(Path("local_commerce/install.py").read_text())
        fn = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "repair_payment_statuses"
        )
        scope = {"frappe": SimpleNamespace(db=SimpleNamespace(sql=self.db.execute))}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<migration>", "exec"), scope)
        self.repair = scope["repair_payment_statuses"]

    def receipt(self, name, method="Cashfree", status="Reconciled", **changes):
        values = dict(
            name=name,
            payment_method=method,
            payment_status=status,
            payment_entry=name,
            sales_invoice=name,
            gateway_payment_id="verified",
            gateway_accounting_error="",
            gateway_refunded_amount=0,
        )
        values.update(changes)
        self.db.execute(
            "insert into `tabLC Order` values (?,?,?,?,?,?,?,?)", tuple(values.values())
        )
        self.db.execute("insert into `tabPayment Entry` values (?,1,?,?)", (name, name, "Receive"))
        self.db.execute("insert into `tabSales Invoice` values (?,1,?,0)", (name, name))

    def statuses(self):
        return dict(self.db.execute("select name, payment_status from `tabLC Order`"))

    def test_repair_and_repeat_migration_keep_cashfree_paid(self):
        self.receipt("cashfree")
        self.receipt("already-paid", status="Paid")
        self.receipt("upi", method="Manual UPI", status="Paid")
        self.receipt("cod", method="Cash on Delivery", status="Paid")
        self.repair()
        self.repair()
        self.assertEqual(
            self.statuses(),
            {"cashfree": "Paid", "already-paid": "Paid", "upi": "Paid", "cod": "Reconciled"},
        )

    def test_unverified_refunded_and_accounting_errors_are_not_repaired(self):
        self.receipt("no-provider", gateway_payment_id="")
        self.receipt("refund", gateway_refunded_amount=1)
        self.receipt("accounting", gateway_accounting_error="review")
        self.receipt("no-payment", payment_entry=None)
        self.receipt("no-invoice", sales_invoice=None)
        self.repair()
        self.assertEqual(set(self.statuses().values()), {"Reconciled"})

    def test_draft_cancelled_and_other_orders_receipts_are_not_repaired(self):
        self.receipt("draft")
        self.receipt("cancelled-invoice")
        self.receipt("wrong-order")
        self.db.execute("update `tabPayment Entry` set docstatus=0 where name='draft'")
        self.db.execute("update `tabSales Invoice` set docstatus=2 where name='cancelled-invoice'")
        self.db.execute(
            "update `tabPayment Entry` set lc_order='different' where name='wrong-order'"
        )
        self.repair()
        self.assertEqual(set(self.statuses().values()), {"Reconciled"})
