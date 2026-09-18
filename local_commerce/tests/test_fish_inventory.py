"""ERPNext integration tests: run on a disposable migrated test site."""

from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, today

from local_commerce.services import fish, fish_reports, orders, owner, packing, products
from local_commerce.tests.helpers import add_member, create_user
from local_commerce.tests.test_packed_weights import TestPackedWeights


class TestFishInventory(FrappeTestCase):
    def setUp(self):
        TestPackedWeights.setUp(self)
        frappe.set_user('Administrator')
        self.shop.reload()
        self.shop.shop_type = 'Fish'
        self.shop.fish_wastage_account = self.shop.stock_adjustment_account
        self.shop.save()
        frappe.set_user(self.user.name)
        self.opening = fish.adopt(self.shop.name, self.item, 48, 'adopt-opening-fish-stock-001')
        frappe.set_user(self.customer.name)

    def tearDown(self):
        TestPackedWeights.tearDown(self)

    def request(self):
        return TestPackedWeights.request(self)

    def expire_lot(self, name):
        # Simulate clock progression without enabling any write path in the API.
        frappe.db.set_value('LC Fish Lot', name, 'expires_at',
                            now_datetime() - timedelta(seconds=1))

    def test_expired_stock_cannot_be_ordered_and_wastage_posts_once(self):
        self.expire_lot(self.opening['lot'])
        with self.assertRaises(frappe.ValidationError):
            self.request()
        frappe.set_user(self.user.name)
        result = fish.adjust(self.shop.name, self.item, 'Wastage', 10, 'Expired fish',
                             'fish-wastage-operation-001', lot=self.opening['lot'])
        replay = fish.adjust(self.shop.name, self.item, 'Wastage', 10, 'Expired fish',
                             'fish-wastage-operation-001', lot=self.opening['lot'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(frappe.db.get_value('Stock Entry', result['stock_entry'], 'docstatus'), 1)
        self.assertEqual(owner.balance(self.item, self.shop.warehouse)['actual'], 0)
        report = fish_reports.report(self.shop.name, today(), today())
        self.assertEqual(report['totals']['wastage_kg'], 10)
        self.assertAlmostEqual(report['totals']['wastage_cost'], 1000)
        self.assertAlmostEqual(report['totals']['profit_after_wastage'], -1000)

    def test_reserved_expired_stock_must_be_released_before_wastage(self):
        request = self.request()
        self.expire_lot(self.opening['lot'])
        frappe.set_user(self.user.name)
        with self.assertRaises(frappe.ValidationError):
            fish.adjust(self.shop.name, self.item, 'Wastage', 10, 'Expired fish',
                        'fish-held-wastage-operation-001', lot=self.opening['lot'])
        orders.change(request['name'], 'Cancelled', 'Expired fish; unable to repack')
        fish.adjust(self.shop.name, self.item, 'Wastage', 10, 'Expired fish',
                    'fish-held-wastage-operation-002', lot=self.opening['lot'])
        self.assertEqual(owner.balance(self.item, self.shop.warehouse)['actual'], 0)

    def test_daily_price_changes_keep_order_price_and_native_profit(self):
        request = self.request()
        frappe.set_user(self.user.name)
        item = frappe.get_doc('Item', self.item)
        owner.update_product(self.shop.name, self.item, str(item.modified), item.item_name,
                             price=500, validity_hours=24)
        self.assertGreater(frappe.db.count('LC Fish Price Change', {'shop': self.shop.name}), 0)
        accepted = orders.change(request['name'], 'Accepted')
        final = packing.finalize(request['name'], accepted['modified'], {'0': 1.02, '1': 0.47})
        self.assertAlmostEqual(sum(row['amount'] for row in final['items']), 447)
        orders.change(request['name'], 'Preparing')
        ready = orders.change(request['name'], 'Ready')
        frappe.set_user('Administrator')
        driver = create_user('LC Delivery Person')
        add_member(self.shop.name, driver.name, 'Driver')
        orders.assign_driver(request['name'], driver.name)
        frappe.set_user(driver.name)
        orders.delivery_change(request['name'], 'Picked Up')
        self.assertAlmostEqual(frappe.db.get_value(
            'LC Fish Lot', self.opening['lot'], 'remaining'), 8.51)
        orders.delivery_change(request['name'], 'Out for Delivery')
        frappe.set_user(self.customer.name)
        otp = orders.detail(request['name'])['delivery_otp']
        frappe.set_user(driver.name)
        orders.delivery_change(request['name'], 'Delivered', ready['total'], delivery_otp_value=otp)
        frappe.set_user(self.user.name)
        report = fish_reports.report(self.shop.name, today(), today())
        self.assertAlmostEqual(report['totals']['revenue'], 447)
        self.assertAlmostEqual(report['totals']['cost'], 149)
        self.assertAlmostEqual(report['totals']['profit_after_wastage'], 298)

    def test_receipts_do_not_extend_existing_lot_expiry_and_nonfish_are_rejected(self):
        before = frappe.db.get_value('LC Fish Lot', self.opening['lot'], 'expires_at')
        frappe.set_user(self.user.name)
        fish.adjust(self.shop.name, self.item, 'Add', 2, 'Morning fish market receipt',
                    'fish-new-receipt-operation-001', unit_cost=120, validity_hours=24)
        self.assertEqual(frappe.db.get_value(
            'LC Fish Lot', self.opening['lot'], 'expires_at'), before)
        self.assertEqual(len(fish.lots(self.shop)), 2)
        self.assertFalse(fish.enabled(frappe._dict(shop_type='General')))
        with self.assertRaises(frappe.PermissionError):
            fish.protect_record(frappe.get_doc('LC Fish Lot', self.opening['lot']))

    def test_piece_item_receipt_sale_and_expiry_without_packed_weight(self):
        frappe.set_user(self.user.name)
        item = products.create_item(self.shop.name, 'Mackerel pieces', self.group, 'Nos')['name']
        fish.adjust(self.shop.name, item, 'Add', 50, 'Fifty fish for four hundred',
                    'piece-receipt-test-0001', unit_cost=8, validity_hours=24)
        product = frappe.get_doc('Item', item)
        owner.update_product(self.shop.name, item, str(product.modified), product.item_name,
                             price=12, validity_hours=24)
        self.assertEqual(owner.detail(self.shop.name, item)['selling_options'], [])
        with self.assertRaises(frappe.ValidationError):
            fish.adjust(self.shop.name, item, 'Remove', 0.5, 'Invalid half piece',
                        'piece-fraction-test-0001')
        frappe.set_user(self.customer.name)
        request = orders.place(self.shop.name, [{'item': item, 'quantity': 6}],
                               self.address, 'piece-order-test-0001')
        self.assertFalse(request['estimated'])
        frappe.set_user(self.user.name)
        product.reload()
        owner.update_product(self.shop.name, item, str(product.modified), product.item_name,
                             price=20, validity_hours=24)
        self.assertEqual(owner.detail(self.shop.name, item)['stock']['available'], 44)
        orders.change(request['name'], 'Accepted')
        orders.change(request['name'], 'Preparing')
        ready = orders.change(request['name'], 'Ready')
        frappe.set_user('Administrator')
        driver = create_user('LC Delivery Person')
        add_member(self.shop.name, driver.name, 'Driver')
        orders.assign_driver(request['name'], driver.name)
        frappe.set_user(driver.name)
        orders.delivery_change(request['name'], 'Picked Up')
        self.assertEqual(owner.balance(item, self.shop.warehouse)['actual'], 44)
        orders.delivery_change(request['name'], 'Out for Delivery')
        frappe.set_user(self.customer.name)
        otp = orders.detail(request['name'])['delivery_otp']
        frappe.set_user(driver.name)
        orders.delivery_change(request['name'], 'Delivered', ready['total'], delivery_otp_value=otp)
        frappe.set_user(self.user.name)
        lot = fish.lots(self.shop, item)[0]
        self.expire_lot(lot.name)
        fish.adjust(self.shop.name, item, 'Wastage', 4, 'Expired four fish',
                    'piece-waste-test-0001', lot=lot.name)
        report = fish_reports.report(self.shop.name, today(), today())
        row = next(row for row in report['items'] if row['item'] == item)
        self.assertEqual(row['closing_quantity'], 40)
        self.assertEqual(row['revenue'], 72)
        self.assertEqual(row['cost'], 48)
        self.assertEqual(row['wastage_cost'], 32)
        self.assertEqual(row['profit_after_stock_losses'], -8)
