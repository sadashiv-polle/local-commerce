import ast
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

def load(name, **extra):
    node = next(n for n in ast.parse(Path("local_commerce/api/easy_split.py").read_text()).body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    scope = dict(re=re, Decimal=Decimal, InvalidOperation=InvalidOperation,
                 frappe=SimpleNamespace(parse_json=lambda v: json.loads(v) if isinstance(v, str) else v),
                 reject=lambda msg: (_ for _ in ()).throw(ValueError(msg)), VERSION="2026-01-01")
    scope.update(extra)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "easy_split", "exec"), scope)
    return scope[name]

class EasySplitTests(TestCase):
    def test_vendor_bank_preserves_zeroes(self):
        result = load("vendor_payload")(dict(bank=dict(account_number="0012345678", account_holder="Test", ifsc="abcd0123456")))
        self.assertEqual(result["bank"]["account_number"], "0012345678")
        self.assertEqual(result["bank"]["ifsc"], "ABCD0123456")

    def test_vendor_rejects_arbitrary_fields(self):
        for payload in [dict(status="DELETED"), dict(bank=dict(secret="x")), dict(verify_account="false"), []]:
            with self.assertRaises(ValueError):
                load("vendor_payload")(payload)

    def test_transfer_validation(self):
        parse = load("transfer_payload")
        base = dict(transfer_type="ON_DEMAND", transfer_from="VENDOR", transfer_amount="10.50", remark="Test")
        self.assertEqual(parse(base)["transfer_amount"], 10.5)
        for value in ["NaN", "Infinity", "-1", "0", "1.001", "invalid"]:
            with self.assertRaises(ValueError):
                parse({**base, "transfer_amount": value})

    def test_non_admin_blocked_before_access(self):
        db = Mock()
        with self.assertRaises(PermissionError):
            load("execute_transfer", require_platform=Mock(side_effect=PermissionError), frappe=db)("request")
        db.get_doc.assert_not_called()

    def test_repeated_execution_does_not_call_provider(self):
        for status in ["Accepted", "Unconfirmed"]:
            doc = SimpleNamespace(name="request", status=status, response="{}")
            db = Mock(get_doc=Mock(return_value=doc), parse_json=json.loads)
            gateway = Mock()
            result = load("execute_transfer", require_platform=lambda: None, frappe=db, cashfree=gateway)("request")
            self.assertEqual(result["status"], status)
            gateway.request.assert_not_called()

    def test_timeout_leaves_committed_intent(self):
        doc = SimpleNamespace(name="request", status="Draft", gateway_profile="test", vendor_id="vendor",
                              payload='{"transfer_amount":10}', save=Mock())
        db = Mock(get_doc=Mock(return_value=doc), parse_json=json.loads)
        gateway = Mock()
        def fail(*args, **kwargs):
            self.assertEqual(doc.status, "Unconfirmed")
            db.db.commit.assert_called_once()
            raise TimeoutError
        gateway.request.side_effect = fail
        result = load("execute_transfer", require_platform=lambda: None, frappe=db, cashfree=gateway,
                      context=lambda *args: (SimpleNamespace(name="test"), "/vendor"))("request")
        self.assertEqual(result["status"], "Unconfirmed")
        gateway.request.assert_called_once()

    def test_reconciliation_scopes_vendor_and_dates(self):
        gateway = Mock()
        run = load("reconciliation", context=Mock(), cashfree=gateway)
        run("sandbox", "vendor1", "2026-11-01", "2026-11-12")
        payload = gateway.request.call_args.args[3]
        self.assertEqual(payload["filters"]["merchant_vendor_id"], "vendor1")
        self.assertEqual(payload["filters"]["end_date"], "2026-11-12T23:59:59Z")
        gateway.reset_mock()
        for start, end in [("invalid", "2026-11-12"), ("2026-11-12", "2026-11-01"), ("2026-01-01", "2026-11-12")]:
            with self.assertRaises(ValueError):
                run("sandbox", "vendor1", start, end)
        gateway.request.assert_not_called()
