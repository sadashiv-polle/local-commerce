import base64
import hashlib
import hmac
import importlib.util
import json
import logging
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from local_commerce.services.payments.rules import (
    money,
    split_amounts,
    successful_payment,
    valid_signature,
)


class CashfreeRulesTests(unittest.TestCase):
    def test_split_preserves_total_to_paise(self):
        vendor, commission = split_amounts("115.55", "Percentage", "2.5")
        self.assertEqual(str(commission), "2.89")
        self.assertEqual(vendor + commission, money("115.55"))
        self.assertEqual(split_amounts(100, "Fixed", 7), (money(93), money(7)))
        for value in ["NaN", "Infinity", "-1"]:
            with self.assertRaises(ValueError):
                money(value)
        with self.assertRaises(ValueError):
            split_amounts(100, "Fixed", 100)

    def test_signature_requires_exact_bytes_and_correct_secret(self):
        body = b'{"amount":350.00}'
        signature = base64.b64encode(
            hmac.new(b"secret", b"123" + body, hashlib.sha256).digest()
        ).decode()
        self.assertTrue(valid_signature("secret", "123", body, signature))
        self.assertFalse(valid_signature("other", "123", body, signature))
        self.assertFalse(valid_signature("secret", "123", b'{"amount":350}', signature))
        self.assertFalse(valid_signature("secret", "", body, signature))

    def test_only_matching_success_can_mark_paid(self):
        remote = dict(
            order_id="lc_order", order_currency="INR", order_amount=350, order_status="PAID"
        )
        success = dict(
            payment_status="SUCCESS", payment_currency="INR", payment_amount=350, cf_payment_id=42
        )
        self.assertEqual(
            successful_payment(
                remote, [dict(payment_status="FAILED"), success], "lc_order", 350, "INR"
            ),
            "42",
        )
        self.assertIsNone(
            successful_payment(remote, [dict(payment_status="PENDING")], "lc_order", 350, "INR")
        )
        for field, value in [
            ("payment_amount", 349),
            ("payment_currency", "USD"),
            ("cf_payment_id", None),
        ]:
            with self.assertRaises(ValueError):
                successful_payment(remote, [{**success, field: value}], "lc_order", 350, "INR")
        with self.assertRaises(ValueError):
            successful_payment({**remote, "order_id": "other"}, [success], "lc_order", 350, "INR")


class CashfreeSyncTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.orders = Mock()
        owner = Mock()

        def reject(message):
            raise ValueError(message)

        owner.reject.side_effect = reject
        self.modules = patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "requests": Mock(),
                "local_commerce.services.orders": self.orders,
                "local_commerce.services.owner": owner,
                "local_commerce.permissions.scope": Mock(),
            },
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location(
            "cashfree_under_test",
            Path(__file__).resolve().parents[1] / "local_commerce/services/payments/cashfree.py",
        )
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.doc = SimpleNamespace(
            name="order",
            payment_method="Cashfree",
            gateway_refunded_amount=0,
            gateway_profile="sandbox",
            gateway_order_id="lc_order",
            gateway_payment_id=None,
            gateway_accounting_error="",
            payment_entry=None,
            payment_status="Pending",
            status="Requested",
            reload=Mock(),
            gateway_snapshot=json.dumps({"amount": "350.00", "currency": "INR"}),
        )
        self.frappe.get_doc.return_value = self.doc
        self.frappe.db.transaction_writes = 0
        self.frappe.db.sql.return_value = [(1,)]
        self.frappe.local.site = "test-site"
        self.service.locked = Mock(return_value=self.doc)
        self.service.save = Mock()
        self.service.book_payment = Mock(side_effect=self.book)
        self.remote = dict(
            order_id="lc_order", order_amount=350, order_currency="INR", order_status="PAID"
        )
        self.payments = [
            dict(
                payment_status="SUCCESS",
                payment_amount=350,
                payment_currency="INR",
                cf_payment_id=42,
            )
        ]
        self.refunds = []
        self.http_request = self.service.request
        self.service.request = Mock(side_effect=self.request)

    def test_http_400_reports_operation_code_and_reference_without_private_values(self):
        config = SimpleNamespace(
            environment="sandbox",
            client_id="private-client-id",
            get_password=lambda _: "private-client-secret",
        )
        self.frappe.get_doc.return_value = config
        response = Mock(status_code=400)
        response.json.return_value = {
            "code": "customer_phone_invalid",
            "message": "customer_phone 9876543210 invalid private-client-secret",
            "payment_session_id": "private-session",
        }
        self.service.requests.request.return_value = response
        with self.assertRaises(ValueError) as error:
            self.http_request("sandbox", "POST", "/orders", {"private": "payload"}, "lc_order")
        detail = str(error.exception)
        self.assertIn("create payment", detail)
        self.assertIn("customer_phone_invalid", detail)
        self.assertIn("ten-digit", detail)
        sent = self.service.requests.request.call_args.kwargs
        self.assertIn(sent["headers"]["x-request-id"], detail)
        self.assertIn("x-idempotency-key", sent["headers"])
        for private in ("9876543210", "private-client", "private-session", "payload"):
            self.assertNotIn(private, detail)
        self.frappe.logger.return_value.error.assert_called_once_with(detail)

    def test_gateway_failure_is_logged_at_production_error_threshold(self):
        logger = logging.Logger("cashfree-test", level=logging.ERROR)
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        logger.addHandler(handler)
        self.frappe.logger.return_value = logger
        response = Mock(status_code=500)
        response.json.return_value = {"code": "request_failed"}
        with self.assertRaises(ValueError):
            self.service.request_failure(response, "POST", "/orders", "test-reference", ())
        self.assertEqual(len(records), 1)
        self.assertIn("test-reference", records[0].getMessage())
        self.assertIn("request_failed", records[0].getMessage())

    def test_non_json_error_and_secret_in_code_are_not_echoed(self):
        for response in (
            Mock(status_code=502, json=Mock(side_effect=ValueError("HTML response"))),
            Mock(status_code=400, json=Mock(return_value={"code": "secret", "message": ""})),
            Mock(status_code=400, json=Mock(return_value=["unexpected"])),
        ):
            with self.assertRaises(ValueError) as error:
                self.service.request_failure(
                    response, "GET", "/orders/lc_order", "ref", ("secret",)
                )
            self.assertIn("unknown_error", str(error.exception))
            self.assertNotIn("secret", str(error.exception))

    def test_missing_lookup_only_allows_404_not_arbitrary_400(self):
        self.frappe.get_doc.return_value = SimpleNamespace(
            environment="sandbox", client_id="client", get_password=lambda _: "secret"
        )
        response = Mock(status_code=404)
        self.service.requests.request.return_value = response
        self.assertIsNone(self.http_request("sandbox", "GET", "/orders/lc_order", missing=True))
        response.status_code = 400
        response.json.return_value = {"code": "order_id_invalid"}
        with self.assertRaisesRegex(ValueError, "fetch payment order"):
            self.http_request("sandbox", "GET", "/orders/lc_order", missing=True)

    def book(self, doc):
        doc.payment_entry = "PAY-1"
        doc.status = "Accepted"

    def test_creation_500_recovers_existing_session_without_another_post(self):
        payload = {"order_id": "lc_order", "order_amount": 350, "order_currency": "INR"}
        remote = {**self.remote, "order_status": "ACTIVE", "payment_session_id": "session"}
        self.service.request.side_effect = [self.service.CreationUncertain("500"), remote]
        self.assertEqual(self.service.create_payment("sandbox", payload, "lc_order"), remote)
        self.assertEqual([c.args[1] for c in self.service.request.call_args_list], ["POST", "GET"])
        self.service.book_payment.assert_not_called()

    def test_creation_retry_keeps_identical_payload_and_idempotency_key(self):
        payload = {"order_id": "lc_order", "order_amount": 350, "order_currency": "INR"}
        self.service.request.side_effect = [
            self.service.CreationUncertain("timeout"),
            None,
            self.remote,
        ]
        self.service.create_payment("sandbox", payload, "lc_order")
        calls = self.service.request.call_args_list
        self.assertEqual(calls[0], calls[2])
        self.assertEqual(calls[1].args[1], "GET")

    def test_persistent_creation_failure_stops_after_one_retry(self):
        payload = {"order_id": "lc_order", "order_amount": 350, "order_currency": "INR"}
        self.service.request.side_effect = [
            self.service.CreationUncertain("500"),
            None,
            self.service.CreationUncertain("still failed"),
            None,
        ]
        with self.assertRaisesRegex(ValueError, "still failed"):
            self.service.create_payment("sandbox", payload, "lc_order")
        self.assertEqual(self.service.request.call_count, 4)

    def test_recovered_session_must_match_original_amount(self):
        payload = {"order_id": "lc_order", "order_amount": 350, "order_currency": "INR"}
        self.service.request.side_effect = [
            self.service.CreationUncertain("500"),
            {**self.remote, "order_amount": 1},
        ]
        with self.assertRaises(ValueError):
            self.service.create_payment("sandbox", payload, "lc_order")
        self.service.book_payment.assert_not_called()

    def test_validation_errors_do_not_retry_creation(self):
        self.service.request.side_effect = ValueError("invalid phone")
        with self.assertRaisesRegex(ValueError, "invalid phone"):
            self.service.create_payment("sandbox", {"order_id": "lc_order"}, "lc_order")
        self.assertEqual(self.service.request.call_count, 1)

    def test_recovery_lookup_failure_does_not_create_another_order(self):
        self.service.request.side_effect = [
            self.service.CreationUncertain("500"),
            ValueError("lookup unavailable"),
        ]
        with self.assertRaisesRegex(ValueError, "lookup unavailable"):
            self.service.create_payment("sandbox", {"order_id": "lc_order"}, "lc_order")
        self.assertEqual(self.service.request.call_count, 2)

    def test_provider_explanation_redacts_payload_and_escapes_markup(self):
        message = self.service.safe_provider_message(
            "invalid customer Jane Doe jane@example.com 9876543210 token-secret <b>bad URL</b>",
            ("token-secret",),
            {"customer_details": {"customer_name": "Jane Doe"}},
        )
        for value in ("Jane Doe", "jane@example.com", "9876543210", "token-secret", "<b>"):
            self.assertNotIn(value, message)
        self.assertIn("bad URL", message)

    def test_http_failure_enters_recovery_only_for_idempotent_creation(self):
        self.frappe.get_doc.return_value = SimpleNamespace(
            environment="sandbox",
            client_id="client",
            get_password=lambda _: "secret",
        )
        response = Mock(status_code=500)
        response.json.return_value = {"code": "request_failed", "message": "internal failure"}
        self.service.requests.request.return_value = response
        with self.assertRaises(self.service.CreationUncertain):
            self.http_request("sandbox", "POST", "/orders", {}, "key", recover=True)
        with self.assertRaises(ValueError):
            self.http_request("sandbox", "GET", "/orders/lc_order", recover=True)

    def test_transport_timeout_is_recoverable_without_exposing_exception(self):
        self.frappe.get_doc.return_value = SimpleNamespace(
            environment="sandbox",
            client_id="client",
            get_password=lambda _: "secret",
        )
        self.service.requests.RequestException = TimeoutError
        self.service.requests.request.side_effect = TimeoutError("sensitive transport details")
        with self.assertRaises(self.service.CreationUncertain) as error:
            self.http_request("sandbox", "POST", "/orders", {}, "key", recover=True)
        self.assertNotIn("sensitive", str(error.exception))

    def request(self, profile, method, path, **kwargs):
        if path.endswith("/payments"):
            return self.payments
        if path.endswith("/refunds"):
            return self.refunds
        return self.remote

    def test_checkout_uses_saved_mode_and_legacy_orders_keep_splits(self):
        self.doc.customer_user = "payer"
        self.doc.phone = "9876543210"
        self.doc.shop = "fish-world"
        self.frappe.session.user = "payer"
        self.frappe.utils.get_url.return_value = "https://example.com"
        self.frappe.db.get_value.return_value = "sandbox"
        self.service.available = Mock(return_value=True)
        for mode in ("Direct merchant", "Easy Split", None):
            snap = {
                "amount": "350.00",
                "currency": "INR",
                "vendor_id": "saved-vendor",
                "vendor_amount": "315.00",
                "expires_at": "2099-01-01T00:00:00+00:00",
            }
            if mode:
                snap["settlement_mode"] = mode
            self.doc.gateway_snapshot = json.dumps(snap)
            self.service.request = Mock(
                side_effect=[
                    None,
                    {**self.remote, "order_status": "ACTIVE", "payment_session_id": "session-test"},
                ]
            )
            result = self.service.checkout("order")
            self.assertEqual(result["payment_session_id"], "session-test")
            payload = self.service.request.call_args.args[3]
            if mode == "Direct merchant":
                self.assertNotIn("order_splits", payload)
            else:
                self.assertEqual(
                    payload["order_splits"], [{"vendor_id": "saved-vendor", "amount": 315.0}]
                )

    def test_direct_snapshot_ignores_stale_vendor_and_commission(self):
        self.service.validate_shop = Mock()
        shop = Mock(
            cashfree_gateway="sandbox",
            cashfree_vendor_id="old-vendor",
            cashfree_commission_type="Percentage",
            cashfree_commission=20,
            cashfree_commission_account="old-expense",
            cashfree_clearing_account="clearing",
            cashfree_mode_of_payment="Cashfree",
        )
        shop.get.side_effect = lambda field: (
            "Direct merchant" if field == "cashfree_settlement_mode" else None
        )
        self.frappe.as_json.side_effect = json.dumps
        self.frappe.utils.now_datetime.return_value = datetime(2026, 9, 27, 12)
        self.frappe.utils.get_system_timezone.return_value = "Asia/Kolkata"
        self.service.snapshot(
            self.doc, shop, SimpleNamespace(grand_total=350, rounded_total=350, currency="INR")
        )
        snap = json.loads(self.doc.gateway_snapshot)
        self.assertIsNone(snap["vendor_id"])
        self.assertIsNone(snap["commission_account"])
        self.assertEqual(snap["commission"], "0.00")
        self.assertEqual(snap["amount"], "350.00")

    def test_direct_shop_needs_no_vendor_or_commission_account(self):
        values = dict(
            cashfree_enabled=1,
            cashfree_gateway="sandbox",
            cashfree_settlement_mode="Direct merchant",
            company="Fish World",
            cashfree_clearing_account="clearing",
            cashfree_mode_of_payment="Cashfree",
        )
        shop = SimpleNamespace(
            **values, get=values.get, get_doc_before_save=lambda: None, is_new=lambda: False
        )
        account = SimpleNamespace(
            company="Fish World",
            root_type="Asset",
            is_group=0,
            disabled=0,
            account_currency="INR",
            account_type="Bank",
        )
        self.frappe.db.exists.return_value = True
        self.frappe.db.get_value.side_effect = [account, "INR", "Bank"]
        self.service.validate_shop(shop)
        self.assertEqual(self.frappe.db.get_value.call_count, 3)
        values["cashfree_settlement_mode"] = "Easy Split"
        with self.assertRaises(ValueError):
            self.service.validate_shop(shop)

    def test_duplicate_success_posts_accounting_once(self):
        self.service.sync("order", authorize=False)
        self.service.sync("order", authorize=False)
        self.service.book_payment.assert_called_once()
        self.assertEqual(self.doc.payment_status, "Paid")
        self.assertEqual(self.doc.gateway_payment_id, "42")

    def test_bookkeeping_failure_keeps_verified_payment_and_retries(self):
        self.service.book_payment.side_effect = RuntimeError("stock unavailable")
        result = self.service.sync("order", authorize=False)
        self.assertEqual(result["payment_status"], "Paid")
        self.assertTrue(result["accounting_pending"])
        self.frappe.db.rollback.assert_called_once_with(save_point="cashfree_accounting")
        self.service.book_payment.side_effect = self.book
        self.service.sync("order", authorize=False)
        self.assertEqual(self.doc.payment_entry, "PAY-1")
        self.assertEqual(self.doc.gateway_accounting_error, "")

    def test_late_failed_event_does_not_downgrade_paid(self):
        self.doc.payment_status = "Paid"
        self.payments = [dict(payment_status="FAILED")]
        self.remote["order_status"] = "EXPIRED"
        self.service.sync("order", authorize=False)
        self.assertEqual(self.doc.payment_status, "Paid")
        self.service.book_payment.assert_not_called()

    def test_active_payment_session_cannot_be_cancelled(self):
        self.remote["order_status"] = "ACTIVE"
        with self.assertRaises(ValueError):
            self.service.prepare_cancellation(self.doc)
        self.remote["order_status"] = "EXPIRED"
        evidence = self.service.prepare_cancellation(self.doc)
        self.service.request.reset_mock()
        self.service.ensure_cancellable(self.doc, evidence)
        self.service.request.assert_not_called()

    def test_verification_fetches_every_remote_response_before_inventory_locks(self):
        events = []
        self.service.request.side_effect = lambda *a, **kw: (
            events.append("http"),
            self.request(*a, **kw),
        )[1]
        self.service.locked.side_effect = lambda _: (events.append("lock"), self.doc)[1]
        self.service.sync("order", authorize=False)
        self.assertEqual(events, ["http", "http", "http", "lock"])

    def test_provider_failure_takes_no_inventory_locks(self):
        self.service.request.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            self.service.sync("order", authorize=False)
        self.service.locked.assert_not_called()
        self.service.save.assert_not_called()

    def test_checkout_takes_no_inventory_locks(self):
        self.doc.customer_user = "payer"
        self.doc.shop = "fish-world"
        self.frappe.session.user = "payer"
        self.service.available = Mock(return_value=True)
        self.remote.update(order_status="ACTIVE", payment_session_id="test-session")
        self.service.checkout("order")
        self.service.locked.assert_not_called()

    def test_busy_order_never_calls_provider_or_takes_inventory_lock(self):
        self.frappe.db.sql.return_value = [(0,)]
        with self.assertRaisesRegex(ValueError, "being updated"):
            self.service.sync("order", authorize=False)
        self.service.request.assert_not_called()
        self.service.locked.assert_not_called()

    def test_payment_guard_does_not_commit_pending_writes(self):
        self.frappe.db.transaction_writes = 1
        with self.assertRaisesRegex(ValueError, "current transaction"):
            self.service.begin_operation("order")
        self.frappe.db.commit.assert_not_called()
        self.frappe.db.sql.assert_not_called()

    def test_guard_release_is_registered_for_commit_and_full_rollback(self):
        self.service.begin_operation("order")
        self.frappe.db.sql.assert_called_once()
        key = self.frappe.db.sql.call_args.args[1]
        commit_release = self.frappe.db.after_commit.add.call_args.args[0]
        rollback_release = self.frappe.db.after_rollback.add.call_args.args[0]
        self.assertIs(commit_release, rollback_release)
        commit_release()
        self.frappe.db.sql.assert_called_with("select release_lock(%s)", key)

    def test_different_orders_proceed_but_same_order_waits_for_transaction_end(self):
        # Model two DB connections and transaction callbacks; no timing/sleeps.
        held = {}

        def connection():
            db = Mock(transaction_writes=0)
            callbacks = {"commit": [], "rollback": []}

            def finish(kind):
                pending = list(callbacks[kind])
                callbacks["commit"].clear()
                callbacks["rollback"].clear()
                for callback in pending:
                    callback()

            def sql(query, params):
                key = params[0]
                if "get_lock" in query:
                    if key in held:
                        return [(0,)]
                    held[key] = db
                    return [(1,)]
                self.assertIs(held.pop(key), db)
                return [(1,)]

            db.sql.side_effect = sql
            db.commit.side_effect = lambda: finish("commit")
            db.rollback.side_effect = lambda: finish("rollback")
            db.after_commit.add.side_effect = callbacks["commit"].append
            db.after_rollback.add.side_effect = callbacks["rollback"].append
            return db

        first, second = connection(), connection()
        self.frappe.db = first
        self.service.begin_operation("order-a")
        self.frappe.db = second
        self.service.begin_operation("order-b")
        self.assertEqual(len(held), 2)
        second.commit()
        with self.assertRaisesRegex(ValueError, "being updated"):
            self.service.begin_operation("order-a")
        self.frappe.db = first
        first.rollback()
        self.assertFalse(held)
        self.frappe.db = second
        self.service.begin_operation("order-a")
        second.commit()
        self.assertFalse(held)

    def test_cancellation_rechecks_payment_after_preflight(self):
        self.remote["order_status"] = "EXPIRED"
        evidence = self.service.prepare_cancellation(self.doc)
        self.doc.payment_status = "Paid"
        with self.assertRaisesRegex(ValueError, "refund"):
            self.service.ensure_cancellable(self.doc, evidence)
        self.doc.payment_status = "Pending"
        self.doc.gateway_order_id = "changed"
        with self.assertRaisesRegex(ValueError, "details changed"):
            self.service.ensure_cancellable(self.doc, evidence)

    def test_recorded_refund_cannot_disappear_on_later_provider_read(self):
        self.doc.gateway_refunded_amount = 350
        self.doc.payment_status = "Refunded"
        self.service.sync("order", authorize=False)
        self.assertEqual(self.doc.gateway_refunded_amount, 350)
        self.assertEqual(self.doc.payment_status, "Refunded")
        self.service.book_payment.assert_not_called()

    def test_checkout_is_restricted_to_the_order_customer(self):
        self.doc.customer_user = "payer"
        self.frappe.session.user = "someone_else"
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = lambda message, kind: (_ for _ in ()).throw(kind(message))
        with self.assertRaises(PermissionError):
            self.service.checkout("order")
        self.service.request.assert_not_called()

    def test_refund_duplicate_is_not_counted_twice(self):
        refund = dict(
            cf_refund_id="refund1",
            cf_payment_id=42,
            order_id="lc_order",
            refund_currency="INR",
            refund_amount=350,
            refund_status="SUCCESS",
        )
        self.refunds = [refund, refund]
        self.service.sync("order", authorize=False)
        self.assertEqual(self.doc.gateway_refunded_amount, 350)
        self.assertEqual(self.doc.payment_status, "Refunded")
        self.service.book_payment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
