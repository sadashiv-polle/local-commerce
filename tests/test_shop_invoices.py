import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class Doc(SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)
    def get_doc_before_save(self):
        return self.get('previous')


def load(name, **scope):
    tree = ast.parse(Path('local_commerce/services/shop_invoices.py').read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    scope.setdefault('reject', lambda text: (_ for _ in ()).throw(ValueError(text)))
    exec(compile(tree,'invoices','exec'),scope)
    return scope[name]


class ShopInvoiceTests(TestCase):
    def setUp(self):
        self.order = Doc(name='order',shop='shop',sales_order='SO',sales_invoice='SI',customer_user='buyer')
        self.so = Doc(name='SO',company='Legal supplier',customer='Customer')
        self.invoice = Doc(name='SI',company='Legal supplier',customer='Customer',docstatus=1,lc_order='order')
        self.guard = Mock()
        self.frappe = SimpleNamespace(session=Doc(user='buyer'),get_doc=Mock(side_effect=[self.order,self.invoice,self.so]),
            PermissionError=PermissionError,throw=Mock(side_effect=PermissionError))

    def test_customer_can_fetch_own_submitted_invoice(self):
        fn=load('invoice_for_order',frappe=self.frappe,require_shop=self.guard)
        self.assertEqual(fn('order'),(self.order,self.invoice))
        self.guard.assert_not_called()

    def test_other_customer_and_rider_need_shop_access(self):
        for user in ('other customer','rider'):
            self.frappe.session.user=user
            self.frappe.get_doc=Mock(return_value=self.order)
            self.guard.side_effect=PermissionError
            with self.subTest(user=user),self.assertRaises(PermissionError):
                load('invoice_for_order',frappe=self.frappe,require_shop=self.guard)('order')
            self.frappe.get_doc.assert_called_once_with('LC Order','order')

    def test_guest_is_rejected_before_document_lookup(self):
        self.frappe.session.user='Guest'
        with self.assertRaises(PermissionError):
            load('invoice_for_order',frappe=self.frappe,require_shop=self.guard)('order')
        self.frappe.get_doc.assert_not_called()

    def test_mismatched_order_or_shop_or_company_is_rejected(self):
        for change in ({'lc_order':'other'},{'lc_shop':'other'},{'company':'Other legal supplier'},
                       {'customer':'Other buyer'},{'docstatus':0},{'docstatus':2}):
            invoice=Doc(**vars(self.invoice));invoice.__dict__.update(change)
            self.frappe.get_doc=Mock(side_effect=[self.order,invoice,self.so])
            with self.subTest(change=change),self.assertRaises(ValueError):
                load('invoice_for_order',frappe=self.frappe,require_shop=self.guard)('order')

    def test_attribution_keeps_original_shop_name_and_supplier(self):
        invoice=Doc(docstatus=0,lc_order='order',company='Legal supplier',customer='Customer',
            items=[Doc(sales_order='SO')],previous=Doc(docstatus=0,lc_shop='shop',lc_shop_name='Original name'))
        f=SimpleNamespace(get_doc=Mock(side_effect=[self.order,self.so,Doc(name='shop',shop_name='Renamed')]))
        load('attribute_invoice',frappe=f)(invoice)
        self.assertEqual(invoice.lc_shop,'shop')
        self.assertEqual(invoice.lc_shop_name,'Original name')
        self.assertEqual(invoice.company,'Legal supplier')

    def test_posted_attribution_is_immutable(self):
        invoice=Doc(docstatus=1,lc_shop='other',lc_shop_name='Shop',previous=Doc(docstatus=1,lc_shop='shop',lc_shop_name='Shop'))
        with self.assertRaises(ValueError):
            load('attribute_invoice')(invoice)

    def test_unrelated_native_invoice_cannot_claim_a_shop(self):
        with self.assertRaises(ValueError):
            load('attribute_invoice')(Doc(docstatus=0,lc_shop='shop'))

    def test_return_copies_original_brand_without_changing_supplier(self):
        invoice=Doc(docstatus=0,is_return=1,return_against='SI',company='Vendor',customer='Customer')
        original=Doc(company='Vendor',customer='Customer',lc_shop='shop',lc_shop_name='Saved brand')
        load('attribute_invoice',frappe=SimpleNamespace(get_doc=Mock(return_value=original)))(invoice)
        self.assertEqual(invoice.lc_shop_name,'Saved brand')
        self.assertEqual(invoice.lc_shop,'shop')

    def test_shop_list_is_authorized_and_parameterized(self):
        db=SimpleNamespace(sql=Mock(return_value=[]))
        fn=load('listing',frappe=SimpleNamespace(db=db),require_shop=self.guard)
        fn("shop' OR 1=1",20)
        self.guard.assert_called_once_with("shop' OR 1=1")
        self.assertEqual(db.sql.call_args.args[1],("shop' OR 1=1",20))
        self.assertNotIn("shop' OR 1=1", db.sql.call_args.args[0])

    def test_print_privilege_restored_after_pdf_failure(self):
        class Flags(dict):
            __getattr__=dict.get
            __setattr__=dict.__setitem__
        import re
        flags=Flags(ignore_print_permissions=False)
        f=SimpleNamespace(flags=flags,get_print=Mock(side_effect=RuntimeError('PDF unavailable')),
            db=SimpleNamespace(get_value=Mock(return_value='Shop')))
        fn=load('download',frappe=f,invoice_for_order=lambda order:(self.order,self.invoice),PRINT_FORMAT='Local dot Shop Invoice',re=re)
        with self.assertRaises(RuntimeError):fn('order')
        self.assertFalse(flags.ignore_print_permissions)
        self.assertIs(f.get_print.call_args.kwargs['doc'], self.invoice)
