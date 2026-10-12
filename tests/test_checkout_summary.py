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
