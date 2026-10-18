import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


def load(name, **scope):
    source = ast.parse(Path('local_commerce/services/shop_onboarding.py').read_text())
    node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope['reject'] = lambda message: (_ for _ in ()).throw(ValueError(message))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'onboarding','exec'),scope)
    return scope[name]


class OnboardingTests(TestCase):
    def test_reuses_compatible_company_account(self):
        db=Mock();db.get_value.return_value='Existing'
        get_doc=Mock(return_value=SimpleNamespace(root_type='Asset',is_group=0,disabled=0,
            account_currency='INR',account_type='Bank'))
        ensure=load('ensure_account',frappe=SimpleNamespace(db=db,get_doc=get_doc))
        self.assertEqual(ensure('Company','LC Bank','Asset','Bank'),'Existing')
        self.assertEqual(db.get_value.call_args.args[1]['company'],'Company')
        get_doc.assert_called_once_with('Account','Existing')

    def test_conflicting_ledger_is_never_modified(self):
        for change in [dict(disabled=1),dict(is_group=1),dict(account_type='Receivable'),
                       dict(account_currency='USD'),dict(root_type='Liability')]:
            values=dict(root_type='Asset',is_group=0,disabled=0,account_currency='INR',account_type='Bank')
            values.update(change)
            db=Mock();db.get_value.return_value='Existing'
            ensure=load('ensure_account',frappe=SimpleNamespace(db=db,get_doc=Mock(return_value=SimpleNamespace(**values))))
            with self.assertRaises(ValueError):
                ensure('Company','LC Bank','Asset','Bank')

    def test_creates_company_scoped_non_group_ledger(self):
        db=Mock();db.get_value.side_effect=[None,'Asset root']
        created=Mock();created.insert.return_value.name='New account'
        get_doc=Mock(return_value=created)
        ensure=load('ensure_account',frappe=SimpleNamespace(db=db,get_doc=get_doc))
        self.assertEqual(ensure('Company','LC Bank','Asset','Bank'),'New account')
        fields=get_doc.call_args.args[0]
        self.assertEqual(fields['company'],'Company')
        self.assertEqual(fields['parent_account'],'Asset root')
        self.assertEqual(fields['is_group'],0)
        self.assertEqual(fields['account_type'],'Bank')

    def test_missing_root_fails_instead_of_using_other_company(self):
        db=Mock();db.get_value.return_value=None
        ensure=load('ensure_account',frappe=SimpleNamespace(db=db,get_all=Mock(return_value=[])))
        with self.assertRaises(ValueError):
            ensure('Company','LC Bank','Asset','Bank')

    def test_wrong_payment_mode_type_rejected(self):
        db=Mock();db.exists.return_value=True;db.get_value.return_value='Cash'
        mode=load('payment_mode',frappe=SimpleNamespace(db=db))
        with self.assertRaises(ValueError):
            mode('Cashfree','Bank')

    def test_identity_is_saved_without_enabling_gst(self):
        apply=load('apply_details',frappe=SimpleNamespace(parse_json=lambda v:dict(v)))
        shop=SimpleNamespace(gst_number='30ZZZCZ0001Z1ZD',gst_registration='Registered',update=Mock())
        details=dict(legal_name='Demo',address='Goa',city='Panaji',postal_code='403001',state='30',
            shop_type='General',gst_mode='Restaurant 9(5)',commission=7)
        apply(shop,details)
        fields=shop.update.call_args.args[0]
        self.assertEqual(fields['gst_commission_rate'],7)
        self.assertEqual(fields['gst_commission_inclusive'],1)
        self.assertNotIn('gst_enabled',fields)
        for invalid in [dict(state='27'),dict(commission=100),dict(city=''),dict(gst_mode='unknown')]:
            with self.assertRaises(ValueError):
                apply(shop,{**details,**invalid})

    def test_provision_requires_admin_before_database_access(self):
        auth=Mock(side_effect=PermissionError())
        run=load('provision',require_platform=auth)
        with self.assertRaises(PermissionError):
            run(SimpleNamespace(company='Company'))
