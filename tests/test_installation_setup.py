"""Bootstrap safety contracts without requiring a running Frappe site."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SOURCE = Path('local_commerce/services/installation_setup.py')

class Doc(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value
    def set(self, key, value):
        self[key] = value
    def save(self, **kwargs):
        return self


class SetupSafety(unittest.TestCase):
    def setUp(self):
        self.settings = Doc()
        self.db = Mock()
        self.db.exists.return_value = False
        self.frappe = Mock(db=self.db)
        self.frappe.get_single.return_value = self.settings
        self.guard = Mock()
        def reject(message):
            raise ValueError(message)
        self.scope = dict(frappe=self.frappe, require_platform=self.guard,
            ensure_account=Mock(return_value='New ledger'), reject=reject)
        tree = ast.parse(SOURCE.read_text())
        tree.body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))]
        exec(compile(tree, str(SOURCE), 'exec'), self.scope)

    def test_both_endpoints_require_admin_before_reading(self):
        self.guard.side_effect = PermissionError
        for method in ('initialize', 'status'):
            with self.assertRaises(PermissionError): self.scope[method]()
        self.frappe.get_single.assert_not_called()
        self.db.sql.assert_not_called()

    def test_existing_company_requires_confirmation_before_mutation(self):
        self.db.exists.return_value = True
        with self.assertRaisesRegex(ValueError, 'Confirm its identity'):
            self.scope['initialize']()
        self.frappe.get_doc.assert_not_called()
        self.assertFalse(self.settings)

    def test_wrong_confirmation_is_rejected(self):
        self.db.exists.return_value = True
        with self.assertRaises(ValueError): self.scope['initialize']('Another company')
        self.frappe.get_doc.assert_not_called()

    def test_existing_non_indian_company_is_not_modified(self):
        self.settings.gst_company = 'Existing'
        company = Doc(name='Existing', country='USA', default_currency='USD')
        self.frappe.get_doc.return_value = company
        with self.assertRaisesRegex(ValueError, 'India and INR'): self.scope['initialize']()
        self.assertEqual(company.default_currency, 'USD')
        self.scope['ensure_account'].assert_not_called()

    def test_existing_shop_requires_explicit_confirmation(self):
        self.settings.gst_company = 'Existing'
        self.frappe.get_doc.return_value = Doc(name='Existing', country='India', default_currency='INR')
        self.frappe.get_all.return_value = ['existing-shop']
        with self.assertRaisesRegex(ValueError, 'Select and confirm'): self.scope['initialize']()
        self.scope['ensure_account'].assert_not_called()

    def test_vendor_shop_cannot_be_adopted_as_owned(self):
        self.settings.update(gst_company='Existing', setup_shop='shop')
        self.frappe.get_doc.side_effect = [Doc(name='Existing', country='India', default_currency='INR'),
            Doc(company='Vendor', business_model='Third-party vendor')]
        with self.assertRaisesRegex(ValueError, 'no historical data was migrated'):
            self.scope['initialize']()
        self.scope['ensure_account'].assert_not_called()

    def test_configured_accounts_preserved_and_no_duplicate_created(self):
        self.db.exists.return_value = True
        doc = Doc(gst_income='My existing sales account')
        self.scope['_ledger'](doc, 'gst_income', 'Existing', ('Default', 'Income', ''))
        self.assertEqual(doc.gst_income, 'My existing sales account')
        self.scope['ensure_account'].assert_not_called()

    def test_invalid_existing_account_not_overwritten(self):
        doc = Doc(gst_income='Other company account')
        with self.assertRaises(ValueError):
            self.scope['_ledger'](doc, 'gst_income', 'Existing', ('Default', 'Income', ''))
        self.assertEqual(doc.gst_income, 'Other company account')
        self.scope['ensure_account'].assert_not_called()

    def test_failed_automatic_bootstrap_rolls_back_and_keeps_pending(self):
        self.db.get_single_value.return_value = 1
        self.scope['initialize'] = Mock(side_effect=ValueError('missing master'))
        self.scope['resume']()
        self.db.rollback.assert_called_once_with(save_point='local_dot_bootstrap')
        self.db.set_single_value.assert_called_once()
        self.assertEqual(self.db.set_single_value.call_args.args[1], 'setup_message')
        self.db.commit.assert_not_called()

    def test_completed_setup_wizard_does_not_reprovision_existing_site(self):
        self.db.get_single_value.return_value = 0
        self.scope['initialize'] = Mock()
        self.scope['resume']()
        self.scope['initialize'].assert_not_called()

    def test_bootstrap_never_provisions_credentials_or_bank(self):
        mapping = self.scope['PLATFORM_ACCOUNTS'] | self.scope['SHOP_ACCOUNTS']
        self.assertNotIn('gst_bank', mapping)
        self.assertNotIn('cashfree_bank_account', mapping)
        self.assertNotIn('upi_bank_account', mapping)
        source = SOURCE.read_text()
        self.assertNotIn('client_secret', source)
        self.assertNotIn("doctype='Bank Account'", source)

    def test_repeated_setup_preserves_renamed_shop_and_live_settings(self):
        self.settings.update(gst_company='Existing', setup_shop='stable-shop',
            marketplace_name='My renamed marketplace', gst_cost_center='Platform CC', setup_complete=1)
        for field in self.scope['PLATFORM_ACCOUNTS']:
            self.settings[field] = 'Existing ' + field
        shop = Doc(name='stable-shop', shop_name='Renamed Basket', company='Existing',
            business_model='Owned shop', warehouse='My Warehouse', cost_center='My CC',
            selling_price_list='My prices', cashfree_enabled=1, accepting_orders=1,
            gst_number='Preserved identity', cashfree_gateway='Real profile')
        for field in self.scope['SHOP_ACCOUNTS']:
            shop[field] = 'Existing ' + field
        before = dict(shop)
        company = Doc(name='Existing', country='India', default_currency='INR')
        self.frappe.get_doc.side_effect = lambda dt, *args, **kw: company if dt == 'Company' else shop
        self.db.exists.return_value = True
        self.scope['status'] = Mock(return_value={})
        owner = SimpleNamespace(configure=Mock())
        with patch.dict('sys.modules', {'local_commerce.services.owner': owner}):
            self.scope['initialize']()
            self.scope['initialize']()
        self.assertEqual(dict(shop), before)
        self.assertEqual(self.settings.marketplace_name, 'My renamed marketplace')
        self.scope['ensure_account'].assert_not_called()
        self.frappe.get_all.assert_not_called()
        self.assertEqual(self.frappe.get_doc.call_count, 4)
        self.db.commit.assert_not_called()

    def test_upgrade_hook_does_not_bootstrap(self):
        tree = ast.parse(Path('local_commerce/install.py').read_text())
        migrate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'after_migrate')
        self.assertNotIn('installation_setup', ast.unparse(migrate))

if __name__ == '__main__':
    unittest.main()
