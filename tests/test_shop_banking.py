import ast
import re
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


def load(name, **scope):
    source=ast.parse(Path('local_commerce/services/shop_banking.py').read_text())
    node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name==name)
    scope.update(re=re,reject=lambda msg: (_ for _ in ()).throw(ValueError(msg)))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'banking','exec'),scope)
    return scope[name]


class BankingTests(TestCase):
    def setUp(self):
        self.parse=load('parse_details',frappe=SimpleNamespace(parse_json=lambda v:dict(v)))
        self.details=dict(mode='new',bank='Test Bank',holder='Demo Shop',number='00123456789',
                          confirm_number='00123456789',ifsc='ABCD0123456')

    def test_leading_zeroes_and_ifsc_normalization(self):
        result=self.parse({**self.details,'ifsc':'abcd0123456'})
        self.assertEqual(result['number'],'00123456789')
        self.assertEqual(result['ifsc'],'ABCD0123456')
        self.assertNotIn('confirm_number',result)

    def test_invalid_bank_details_rejected(self):
        for changes in [dict(number='123'),dict(confirm_number='123456'),dict(ifsc='ABCD1123456'),
                        dict(ifsc='invalid'),dict(bank=''),dict(holder=''),dict(mode='unsafe'),
                        dict(number='12 3456789'),dict(is_default=1)]:
            with self.assertRaises(ValueError):
                self.parse({**self.details,**changes})

    def test_inactive_inputs_not_used(self):
        self.assertEqual(self.parse({**self.details,'mode':'later'}),{'mode':'later'})
        self.assertEqual(self.parse(dict(mode='existing',existing='Owned Bank',number='ignored')),
                         dict(mode='existing',existing='Owned Bank'))

    def test_existing_requires_selection(self):
        with self.assertRaises(ValueError):
            self.parse(dict(mode='existing'))

    def bank(self, **change):
        data=dict(disabled=0,is_company_account=1,company='Shop Company',account='Bank Ledger',
                  is_credit_card=0,bank_account_no='00123456789',branch_code='ABCD0123456')
        data.update(change)
        bank=SimpleNamespace(**data);bank.get=lambda key:data.get(key)
        return bank

    def check(self, bank, **ledger_changes):
        values=dict(company='Shop Company',disabled=0,is_group=0,root_type='Asset',
                    account_type='Bank',account_currency='INR')
        values.update(ledger_changes)
        get_doc=Mock(side_effect=[bank,SimpleNamespace(**values)])
        fn=load('checked_account',frappe=SimpleNamespace(get_doc=get_doc),ifsc_field=lambda:'branch_code')
        return fn('Owned Bank','Shop Company')

    def test_existing_account_must_belong_to_company(self):
        for change in [dict(company='Other Company'),dict(disabled=1),dict(is_company_account=0),
                       dict(is_credit_card=1),dict(account=None)]:
            with self.assertRaises(ValueError):
                self.check(self.bank(**change))

    def test_existing_ledger_must_be_active_inr_bank(self):
        for change in [dict(company='Other Company'),dict(disabled=1),dict(is_group=1),
                       dict(account_type='Cash'),dict(account_currency='USD'),dict(root_type='Liability')]:
            with self.assertRaises(ValueError):
                self.check(self.bank(),**change)

    def test_existing_account_requires_number_and_ifsc(self):
        for change in [dict(bank_account_no=''),dict(branch_code='invalid')]:
            with self.assertRaises(ValueError):
                self.check(self.bank(**change))
        bank=self.bank()
        self.assertIs(self.check(bank),bank)

    def test_choices_mask_account_number(self):
        row=SimpleNamespace(name='Bank',company='Company',account='Ledger',bank='Demo',bank_account_no='00123456789')
        fn=load('options',require_platform=Mock(),frappe=SimpleNamespace(get_all=Mock(return_value=[row])))
        result=fn()[0]
        self.assertEqual(result['last_four'],'6789')
        self.assertNotIn('bank_account_no',result)
        self.assertNotIn('00123456789',str(result))

    def test_bank_configuration_requires_platform_authority(self):
        fn=load('configure',require_platform=Mock(side_effect=PermissionError()))
        with self.assertRaises(PermissionError):
            fn(SimpleNamespace(),{})

    def test_ifsc_uses_installed_field_or_native_branch_code(self):
        for fields, expected in [({'ifsc_code'},'ifsc_code'),({'ifsc'},'ifsc'),(set(),'branch_code')]:
            fn=load('ifsc_field',frappe=SimpleNamespace(get_meta=lambda _:SimpleNamespace(has_field=lambda f:f in fields)))
            self.assertEqual(fn(),expected)

class BankSwitchTests(TestCase):
    def run_switch(self, usage):
        values={'upi_bank_account':'Old UPI','cashfree_bank_account':'Old settlement'}
        doc=SimpleNamespace(company='Shop',upi_bank_account=values['upi_bank_account'],
                            cashfree_bank_account=values['cashfree_bank_account'],get=values.get,save=Mock())
        def configure(shop, details):
            shop.upi_bank_account='New Bank';shop.cashfree_bank_account='New Bank'
            return 'New native record'
        db=SimpleNamespace(get_value=Mock(return_value='Shop'))
        fn=load('save_shop_bank',require_platform=Mock(),parse_details=lambda x:x,configure=configure,
                frappe=SimpleNamespace(db=db,get_doc=Mock(side_effect=[SimpleNamespace(),doc])))
        result=fn('Shop ID',{'mode':'existing','existing':'New native record'},usage)
        return doc,result

    def test_save_only_does_not_change_shop_accounts(self):
        doc,result=self.run_switch('store')
        self.assertEqual(doc.upi_bank_account,'Old UPI')
        self.assertEqual(doc.cashfree_bank_account,'Old settlement')
        doc.save.assert_not_called()
        self.assertEqual(result['bank_account'],'New native record')

    def test_switch_upi_preserves_settlement(self):
        doc,_=self.run_switch('upi')
        self.assertEqual(doc.upi_bank_account,'New Bank')
        self.assertEqual(doc.cashfree_bank_account,'Old settlement')
        doc.save.assert_called_once()

    def test_switch_settlement_preserves_upi(self):
        doc,_=self.run_switch('settlement')
        self.assertEqual(doc.upi_bank_account,'Old UPI')
        self.assertEqual(doc.cashfree_bank_account,'New Bank')

    def test_both_switches_explicitly(self):
        doc,_=self.run_switch('both')
        self.assertEqual(doc.upi_bank_account,'New Bank')
        self.assertEqual(doc.cashfree_bank_account,'New Bank')

    def test_invalid_usage_rejected(self):
        fn=load('save_shop_bank',require_platform=Mock())
        with self.assertRaises(ValueError):
            fn('Shop',{},'invalid')

    def test_only_admin_can_manage_bank_accounts(self):
        for name in ('shop_settings','save_shop_bank'):
            fn=load(name,require_platform=Mock(side_effect=PermissionError()))
            with self.assertRaises(PermissionError):
                fn('Shop',{}) if name=='save_shop_bank' else fn('Shop')
