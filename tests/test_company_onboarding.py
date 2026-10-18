import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

class Doc(SimpleNamespace):
    def get(self,key): return getattr(self,key,None)

def functions(frappe, guard):
    tree=ast.parse(Path('local_commerce/services/business_structure.py').read_text())
    tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    scope=dict(frappe=frappe,require_platform=guard)
    exec(compile(tree,'structure','exec'),scope)
    return scope

class CompanyOnboardingTests(TestCase):
    def setUp(self):
        self.guard=Mock()
        self.db=Mock()
        self.db.exists.return_value=False
        self.frappe=Mock(db=self.db)
        self.frappe.throw.side_effect=ValueError
        self.frappe.generate_hash.return_value='abcd1234'
        self.scope=functions(self.frappe,self.guard)
        self.shop=Doc(business_model='Third-party vendor',gst_legal_name='Vendor Legal',
            company_country='India',company_currency='INR',gst_registration='Unregistered')

    def test_vendor_company_uses_legal_name_not_brand(self):
        self.frappe.get_doc.return_value.name='Vendor Legal'
        self.scope['create_vendor_company'](self.shop)
        payload=self.frappe.get_doc.call_args.args[0]
        self.assertEqual(payload['company_name'],'Vendor Legal')
        self.assertEqual(payload['default_currency'],'INR')
        self.assertEqual(self.shop.company,'Vendor Legal')
        self.frappe.get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)
        self.db.commit.assert_not_called()

    def test_owned_shop_never_creates_a_company(self):
        self.shop.business_model='Owned shop'
        with self.assertRaises(ValueError):self.scope['create_vendor_company'](self.shop)
        self.frappe.get_doc.assert_not_called()

    def test_duplicate_company_requires_explicit_selection(self):
        self.db.exists.return_value=True
        with self.assertRaises(ValueError):self.scope['create_vendor_company'](self.shop)
        self.frappe.get_doc.assert_not_called()

    def test_non_admin_cannot_create_company(self):
        self.guard.side_effect=PermissionError
        with self.assertRaises(PermissionError):self.scope['create_vendor_company'](self.shop)
        self.db.exists.assert_not_called()

    def test_existing_platform_cannot_be_silently_replaced(self):
        self.db.get_single_value.return_value='Platform'
        self.db.exists.return_value=True
        with self.assertRaises(ValueError):self.scope['select_platform']('Other')
        self.frappe.get_single.assert_not_called()

    def test_platform_identity_saved_without_tax_activation(self):
        self.db.get_single_value.return_value=None
        self.db.exists.return_value=True
        self.assertEqual(self.scope['select_platform']('Platform'),'Platform')
        settings=self.frappe.get_single.return_value
        self.assertEqual(settings.gst_company,'Platform')
        settings.save.assert_called_once_with(ignore_permissions=True)

    def test_platform_change_with_classified_shops_rejected(self):
        self.db.exists.return_value=True
        doc=Doc(gst_company='New',get_doc_before_save=lambda:Doc(gst_company='Old'))
        with self.assertRaises(ValueError):self.scope['validate_platform_change'](doc)
