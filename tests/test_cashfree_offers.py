import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from local_commerce.services.payments.rules import money, offer_receipt_allocation

# Exercise the pure provider evidence validator without a Frappe site.
source = ast.parse(Path("local_commerce/services/payments/offers.py").read_text())
namespace = {"money": money}
exec(
    compile(
        ast.Module(
            body=[
                n
                for n in source.body
                if isinstance(n, ast.FunctionDef) and n.name == "settlement_observation"
            ],
            type_ignores=[],
        ),
        "offers.py",
        "exec",
    ),
    namespace,
)
observe = namespace["settlement_observation"]


class OfferEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.payment = dict(
            currency="INR", order_amount="210", payment_amount="160", discount_amount="50"
        )
        self.payload = dict(
            order_details=dict(order_id="order", order_currency="INR", order_amount=210),
            payment_details=dict(
                cf_payment_id="payment",
                payment_currency="INR",
                payment_amount=160,
                charge_type="PREPAID",
                charged_to="MERCHANT",
                pg_service_charge=2,
                pg_service_tax=0,
                split_service_charge=0,
                split_service_tax=0,
                settlement_amount=158,
            ),
            settlement_details=dict(
                status="SUCCESS",
                settlement_currency="INR",
                cf_settlement_id="settlement",
                settlement_utr="utr",
                settlement_processed_on="2026-10-29",
            ),
        )

    def test_customer_cash_does_not_prove_offer_reimbursement(self):
        self.assertEqual(
            observe(self.payload, self.payment, "order", "payment")[
                "amount_above_customer_payment"
            ],
            "0.00",
        )
        self.payload["payment_details"]["settlement_amount"] = 208
        self.assertEqual(
            observe(self.payload, self.payment, "order", "payment")[
                "amount_above_customer_payment"
            ],
            "50.00",
        )

    def test_unexplained_adjustments_and_unrelated_payments_rejected(self):
        for amount in (157, 209):
            self.payload["payment_details"]["settlement_amount"] = amount
            with self.assertRaises(ValueError):
                observe(self.payload, self.payment, "order", "payment")
        self.payload["payment_details"]["settlement_amount"] = 158
        with self.assertRaises(ValueError):
            observe(self.payload, self.payment, "order", "other-payment")
        self.payload["settlement_details"]["settlement_utr"] = "N/A"
        with self.assertRaises(ValueError):
            observe(self.payload, self.payment, "order", "payment")

    def test_funding_confirmation_required_before_receivable_posting(self):
        data = dict(payment_evidence=self.payment)
        doc = SimpleNamespace(
            gateway_accounting_json=json.dumps(data),
            gateway_payment_id="payment",
            gateway_snapshot=json.dumps(dict(amount=210, settlement_mode="Direct merchant")),
        )
        doc.get = lambda key: getattr(doc, key, None)
        with self.assertRaises(ValueError):
            offer_receipt_allocation(doc)
        data["offer_funding"] = dict(
            account="Offer receivable",
            provider="Bank",
            evidence="Written agreement",
            amount=50,
            payment_id="payment",
        )
        doc.gateway_accounting_json = json.dumps(data)
        self.assertEqual(offer_receipt_allocation(doc)["payment_amount"], "160.00")
        doc.gst_snapshot = "{}"
        with self.assertRaises(ValueError):
            offer_receipt_allocation(doc)
        doc.gst_snapshot = None
        doc.gateway_payment_id = "unrelated"
        with self.assertRaises(ValueError):
            offer_receipt_allocation(doc)
