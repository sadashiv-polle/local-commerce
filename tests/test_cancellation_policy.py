import unittest
from local_commerce.services.cancellation_policy import allocation, fee_evidence, paise, percentage, rupees


class CancellationPolicyTests(unittest.TestCase):
    def test_conversion_is_exact_and_rejects_bad_money(self):
        self.assertEqual(paise('123.45'), 12345)
        self.assertEqual(rupees(12345), '123.45')
        for value in ('NaN', 'Infinity', '-1', '.001', None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                paise(value)

    def test_customer_before_preparing(self):
        a = allocation(100000, 2360, 'Customer before preparing')
        self.assertEqual(a['refund_paise'], 97640)
        self.assertEqual(a['vendor_paise'], 0)
        self.assertEqual(a['commission_paise'], 0)

    def test_shop_cancellation_refunds_full_amount(self):
        a = allocation(100000, 2360, 'Shop cancellation')
        self.assertEqual(a['refund_paise'], 100000)
        self.assertEqual(a['shop_debt_paise'], 2360)

    def test_post_preparation_no_commission(self):
        a = allocation(100000, 2360, 'Approved customer request')
        self.assertEqual(a['refund_paise'], 85000)
        self.assertEqual(a['compensation_paise'], 15000)
        self.assertEqual(a['vendor_paise'], 12640)
        self.assertEqual(a['commission_paise'], 0)

    def test_paise_conservation_and_rounding(self):
        for paid in (0, 1, 7, 101, 19999, 100000):
            for fee in (0, 1, 236, 999999):
                for kind in ('Shop cancellation','Customer before preparing','Approved customer request'):
                    a = allocation(paid, fee, kind)
                    self.assertEqual(paid + a['shop_debt_paise'], a['refund_paise'] + a['vendor_paise'] + fee)
                    self.assertGreaterEqual(a['refund_paise'], 0)
        a = allocation(101, 100, 'Approved customer request')
        self.assertEqual(a['refund_paise'], 86)
        self.assertEqual(a['compensation_paise'], 15)
        self.assertEqual(a['shop_debt_paise'], 85)
        self.assertEqual(percentage(10000, 700), 700)

    def evidence(self):
        return {'cursor':None,'data':[dict(merchant_order_id='o',entity_type='transaction',entity_id='p',
            currency='INR',sale_type='CREDIT',amount='1000',pg_service_charge='20',pg_service_tax='3.60',
            split_service_charge='1',split_service_tax='.18')]}

    def test_fee_includes_only_verified_actual_components(self):
        result = fee_evidence(self.evidence(), 'o', 'p', 100000)
        self.assertEqual(result['total_paise'], 2478)
        self.assertEqual(result['tax_paise'], 360)

    def test_missing_fee_is_not_zero(self):
        for key in ('pg_service_charge','pg_service_tax','split_service_charge','split_service_tax'):
            data = self.evidence(); del data['data'][0][key]
            with self.assertRaises((ValueError,KeyError)):
                fee_evidence(data,'o','p',100000)

    def test_wrong_or_incomplete_evidence_fails_closed(self):
        for data in ({'data':[]}, dict(self.evidence(),cursor='next'),
                     {'data':self.evidence()['data'] * 2}):
            with self.assertRaises(ValueError):
                fee_evidence(data,'o','p',100000)
        for order,payment,paid in (('x','p',100000),('o','x',100000),('o','p',999)):
            with self.assertRaises(ValueError):
                fee_evidence(self.evidence(),order,payment,paid)


class DeliveryAllocationTests(unittest.TestCase):
    def test_seven_percent_with_separate_gst(self):
        from local_commerce.services.cancellation_policy import delivery_allocation
        result = delivery_allocation(108000, base=100000, gst_bps=1800)
        self.assertEqual(result['commission_paise'], 7000)
        self.assertEqual(result['commission_gst_paise'], 1260)
        self.assertEqual(result['vendor_paise'], 99740)

    def test_inclusive_gst_and_retained_supply_gst(self):
        from local_commerce.services.cancellation_policy import delivery_allocation
        result = delivery_allocation(105000, base=100000, gst_bps=1800, inclusive=True, retained_gst=5000)
        self.assertEqual(result['commission_gross_paise'], 7000)
        self.assertEqual(result['commission_paise'], 5932)
        self.assertEqual(result['commission_gst_paise'], 1068)
        self.assertEqual(result['vendor_paise'], 93000)
        self.assertEqual(sum(result[k] for k in ('vendor_paise','commission_paise','commission_gst_paise','retained_gst_paise')),105000)
