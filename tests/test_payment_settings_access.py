import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class PaymentSettingsAccessTests(unittest.TestCase):
    def test_settings_endpoints_deny_non_admin_before_access(self):
        guard = Mock(side_effect=PermissionError)
        with patch.dict(
            sys.modules,
            {"local_commerce.permissions.scope": SimpleNamespace(require_platform=guard)},
        ):
            for path, functions in [
                ("local_commerce/services/manual_upi.py", ["settings", "configure", "upload_qr"]),
                ("local_commerce/services/orders.py", ["payment_options", "configure_cod"]),
            ]:
                source = ast.parse(Path(path).read_text())
                source.body = [
                    node
                    for node in source.body
                    if isinstance(node, ast.FunctionDef) and node.name in functions
                ]
                scope = {}
                exec(compile(source, path, "exec"), scope)
                for name in functions:
                    with self.subTest(endpoint=name), self.assertRaises(PermissionError):
                        args = ("shop", 1) if name == "configure_cod" else ("shop",)
                        scope[name](*args)

    def test_direct_shop_updates_deny_all_payment_field_groups(self):
        path = "local_commerce/local_commerce/doctype/lc_shop/lc_shop.py"
        tree = ast.parse(Path(path).read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        validate = next(
            node
            for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name == "validate"
        )
        scope = {
            "identity": lambda: ("owner", []),
            "is_platform": lambda *args: False,
            "require_shop": Mock(),
            "frappe": SimpleNamespace(
                throw=Mock(side_effect=PermissionError), PermissionError=PermissionError
            ),
        }
        exec(compile(ast.Module(body=[validate], type_ignores=[]), path, "exec"), scope)
        for field in ["cod_enabled", "upi_id", "upi_qr", "cashfree_gateway"]:
            previous = Mock(company="company")
            previous.get.return_value = "old"
            doc = Mock(name="shop", company="company")
            doc.get.side_effect = lambda key: "Manual" if key == "order_acceptance" else "new"
            doc.get_doc_before_save.return_value = previous
            doc.meta.fields = [SimpleNamespace(fieldname=field)]
            with self.subTest(field=field), self.assertRaises(PermissionError):
                scope["validate"](doc)
