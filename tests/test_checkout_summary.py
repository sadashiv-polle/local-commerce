import unittest
from types import SimpleNamespace
from local_commerce.services.checkout_summary import checkout_bill


class CheckoutSummaryTests(unittest.TestCase):
    def bill(self, subtotal=350, discount=0, fee=20, total=370):
        return checkout_bill(SimpleNamespace(total=subtotal, discount_amount=discount,
            grand_total=total, taxes=[SimpleNamespace(description='Delivery charge', tax_amount=fee)]))

    def test_saved_tax_discount_and_delivery_balance_to_payable(self):
        bill = self.bill(discount=35, total=353)
        self.assertEqual(bill['taxes'], 18)
        self.assertEqual(bill['subtotal'] + bill['delivery'] + bill['taxes'] - bill['discount'], 353)

    def test_free_scheduled_delivery(self):
        self.assertEqual(self.bill(fee=0, total=350)['delivery'], 0)

    def test_inclusive_tax_is_not_added_twice(self):
        self.assertEqual(self.bill()['taxes'], 0)

    def test_decimal_totals(self):
        bill = self.bill(subtotal=349.99, discount=10.55, fee=15.5, total=362.12)
        self.assertAlmostEqual(bill['subtotal'] + bill['delivery'] + bill['taxes'] - bill['discount'], 362.12)


class PreparedOrderTests(unittest.TestCase):
    def test_preview_is_unsaved_and_uses_same_template_and_delivery(self):
        import sys
        from unittest.mock import Mock, patch
        from local_commerce.services.checkout_summary import prepare_sales_order
        frappe = Mock()
        so = frappe.get_doc.return_value
        taxes = Mock(return_value=[{'charge_type': 'On Net Total', 'rate': 5}])
        modules = {'frappe': frappe, 'frappe.utils': SimpleNamespace(nowdate=lambda: '2026-10-13'),
                   'erpnext.controllers.accounts_controller': SimpleNamespace(get_taxes_and_charges=taxes)}
        shop = SimpleNamespace(company='Shop', selling_price_list='Retail', warehouse='Stock',
                               order_tax_template='GST', delivery_account='Delivery')
        with patch.dict(sys.modules, modules):
            result = prepare_sales_order(shop, [{'item_code': 'fish', 'qty': 1, 'rate': 350}],
                                         'Customer', '2026-10-13', 20)
        self.assertIs(result, so)
        taxes.assert_called_once_with('Sales Taxes and Charges Template', 'GST')
        so.set_missing_values.assert_called_once()
        so.append.assert_called_once_with('taxes', dict(charge_type='Actual', account_head='Delivery',
                                                       description='Delivery charge', tax_amount=20))
        so.insert.assert_not_called()
        so.save.assert_not_called()

    def test_owned_shop_uses_its_cost_center_for_items_and_delivery(self):
        import sys
        from unittest.mock import Mock, patch
        from local_commerce.services.checkout_summary import prepare_sales_order
        frappe = Mock()
        so = frappe.get_doc.return_value
        so.items = [SimpleNamespace()]
        so.taxes = [SimpleNamespace(description='Delivery charge')]
        modules = {'frappe': frappe, 'frappe.utils': SimpleNamespace(nowdate=lambda:'2026-10-18'),
                   'erpnext.controllers.accounts_controller': SimpleNamespace(get_taxes_and_charges=Mock())}
        shop = SimpleNamespace(company='Legal company',selling_price_list='Shop prices',warehouse='Shop stock',
            order_tax_template=None,delivery_account='Delivery',business_model='Owned shop',cost_center='Shop centre')
        with patch.dict(sys.modules,modules):
            prepare_sales_order(shop,[],None,'2026-10-18',0)
        self.assertEqual(so.cost_center,'Shop centre')
        self.assertTrue(all(row.cost_center=='Shop centre' for row in [*so.items,*so.taxes]))
