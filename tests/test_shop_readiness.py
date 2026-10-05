import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.guard = Mock()
        self.doc = SimpleNamespace(company='Company', status='Active', accepting_orders=1,
            service_radius_km=5, warehouse='Warehouse', cost_center='Cost', stock_adjustment_account='Expense',
            selling_price_list='Prices', cod_enabled=1, cod_cash_account='Cash', cod_mode_of_payment='Cash',
            upi_enabled=0, cashfree_enabled=0, delivery_enabled=1, scheduled_enabled=0, opening_hours_json='')
        self.frappe.get_doc.return_value = self.doc
        self.frappe.get_all.return_value = ['owner']
        self.frappe.get_roles.return_value = ['LC Shop Owner', 'LC Delivery Person']
        self.frappe.db.exists.return_value = True
        catalog = Mock(return_value={'items': [{'lc_sold_out': False, 'stock': {'available': 2}, 'price': 50}], 'total': 1})
        modules = {'frappe': self.frappe, 'local_commerce.permissions.scope': SimpleNamespace(require_platform=self.guard),
            'local_commerce.services.locations': SimpleNamespace(shop_location=lambda d: {'latitude': 1}),
            'local_commerce.services.owner': SimpleNamespace(catalog=catalog)}
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start(); self.addCleanup(self.patch.stop)
        spec = importlib.util.spec_from_file_location('readiness_test', Path('local_commerce/services/shop_readiness.py'))
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)

    def test_admin_required_before_reading_shop(self):
        self.guard.side_effect = PermissionError
        with self.assertRaises(PermissionError): self.module.readiness('shop')
        self.frappe.get_doc.assert_not_called()

    def test_ready_configuration(self):
        result = self.module.readiness('shop')
        self.assertEqual(result['passed'], result['total'])

    def test_disabled_modes_and_payment_are_flagged(self):
        self.doc.cod_enabled = 0; self.doc.delivery_enabled = 0
        result = self.module.readiness('shop')
        flags = {row['label']: row['ready'] for row in result['checks']}
        self.assertFalse(flags['Payment method configured'])
        self.assertFalse(flags['Delivery mode enabled'])
