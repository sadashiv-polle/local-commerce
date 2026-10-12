import importlib.util
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.session.user = 'rider@example.com'
        self.frappe.throw.side_effect = ValueError
        self.guard = Mock()
        self.driver = Mock()
        modules = {'frappe': self.frappe, 'frappe.utils': SimpleNamespace(now_datetime=lambda: 'now'),
                   'local_commerce.permissions.scope': SimpleNamespace(require_platform=self.guard),
                   'local_commerce.services.orders': SimpleNamespace(driver_shops=self.driver)}
        self.patch = patch.dict(sys.modules, modules); self.patch.start(); self.addCleanup(self.patch.stop)
        spec = importlib.util.spec_from_file_location('operations_test', 'local_commerce/services/operations.py')
        self.ops = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.ops)

    def test_admin_denied_before_any_query(self):
        self.guard.side_effect = PermissionError
        for action in [self.ops.attention, self.ops.rider_rates]:
            with self.assertRaises(PermissionError): action()
        self.frappe.db.sql.assert_not_called()

    def test_category_cannot_inject_sql(self):
        with self.assertRaises(ValueError): self.ops.attention("unpaid'; drop table orders")
        self.frappe.db.sql.assert_not_called()

    def test_counts_are_independent_and_listing_paged(self):
        self.frappe.db.sql.side_effect = [[[7]], [[2]], [[3]], [[4]], [[5]], [dict(name=str(n)) for n in range(21)]]
        result = self.ops.attention('expired', 20, "shop' OR 1=1")
        self.assertEqual(result['counts']['unpaid'], 7)
        self.assertEqual(len(result['items']), 20)
        self.assertTrue(result['has_more'])
        query, params = self.frappe.db.sql.call_args.args
        self.assertNotIn("shop' OR", query)
        self.assertEqual(params['shop'], "shop' OR 1=1")

    def test_rider_cannot_request_someone_elses_totals(self):
        self.frappe.db.sql.return_value = []
        self.ops.rider_totals()
        self.driver.assert_called_once_with('rider@example.com')
        for call in self.frappe.db.sql.call_args_list:
            self.assertEqual(call.args[1], {'user': 'rider@example.com'})
        self.assertIn('reconciled_at is null', self.frappe.db.sql.call_args.args[0])

    def test_invalid_rate_never_saved(self):
        for amount in ['nan', 'inf', -1, 100001]:
            with self.assertRaises(ValueError): self.ops.rider_rates('shop', amount)
        self.frappe.get_doc.assert_not_called()
