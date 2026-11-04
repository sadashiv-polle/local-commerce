import importlib.util
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.session.user = "admin"
        self.frappe.conf = {}
        self.frappe.AuthenticationError = PermissionError
        self.frappe.throw.side_effect = PermissionError
        self.scope = Mock()
        owner = Mock()
        owner.reject.side_effect = ValueError
        self.now = datetime(2026, 10, 30, 12)
        modules = patch.dict(sys.modules, {
            "frappe": self.frappe,
            "frappe.utils": SimpleNamespace(now_datetime=lambda: self.now, get_datetime=lambda value: value),
            "local_commerce.permissions.scope": self.scope,
            "local_commerce.services.owner": owner,
        })
        modules.start()
        template_spec = importlib.util.spec_from_file_location('template_test', Path('local_commerce/services/campaign_templates.py'))
        self.templates = importlib.util.module_from_spec(template_spec)
        template_spec.loader.exec_module(self.templates)
        self.frappe.db.get_single_value.return_value = None
        template_patch = patch.dict(sys.modules, {'local_commerce.services.campaign_templates': self.templates})
        template_patch.start()
        self.addCleanup(template_patch.stop)
        self.addCleanup(modules.stop)
        spec = importlib.util.spec_from_file_location("campaign_test", Path("local_commerce/services/campaigns.py"))
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.doc = SimpleNamespace(name="campaign", status="Queued", shop="shop", item="",
                                   send_at=self.now, recipients=json.dumps(["a", "b", "c"]),
                                   cursor=0, queued_count=0, skipped_count=0)
        self.doc.get = lambda key: getattr(self.doc, key, None)
        self.frappe.get_doc.return_value = self.doc
        self.service._target = Mock()
        self.service.shop_is_open = Mock(return_value=True)
        self.original_notify = self.service._notify
        self.service._notify = Mock()

    def test_manual_campaign_has_no_frequency_limit_but_respects_opt_out(self):
        self.service.allowed = Mock(side_effect=[True, False, True])
        self.frappe.db.count.side_effect = [0, 0, 1]
        self.service.process_one("campaign")
        self.assertEqual(self.service._notify.call_count, 2)
        values = self.frappe.db.set_value.call_args.args[2]
        self.assertEqual(values, {"cursor": 3, "queued_count": 2, "skipped_count": 1, "status": "Completed"})

    def test_unlimited_testing_bypasses_cap_but_respects_opt_out(self):
        self.frappe.conf = {"lc_campaign_unlimited_testing": 1}
        self.service.allowed = Mock(side_effect=[True, False, True])
        self.frappe.db.count.return_value = 100
        self.service.process_one("campaign")
        self.assertEqual(self.service._notify.call_count, 2)
        self.assertEqual(self.frappe.db.set_value.call_args.args[2]["skipped_count"], 1)

    def test_completed_campaign_does_not_send_again(self):
        self.doc.status = "Completed"
        self.service.process_one("campaign")
        self.service._notify.assert_not_called()

    def test_closed_shop_and_future_schedule_wait(self):
        self.service.shop_is_open.return_value = False
        self.service.process_one("campaign")
        self.service.shop_is_open.return_value = True
        self.doc.send_at = datetime(2026, 10, 31, 12)
        self.service.process_one("campaign")
        self.service._notify.assert_not_called()
        self.frappe.db.set_value.assert_not_called()

    def test_repeat_send_preserves_existing_queue(self):
        self.assertEqual(self.service.send("campaign"), {"status": "Queued"})
        self.frappe.db.set_value.assert_not_called()

    def test_only_consented_users_in_snapshot(self):
        self.doc.status = "Draft"
        self.frappe.get_all.return_value = ["opted-in"]
        self.service.send("campaign")
        self.frappe.get_all.assert_any_call(
            "LC Promotion Preference", filters={"enabled": 1}, pluck="user", limit_page_length=0)
        values = self.frappe.db.set_value.call_args.args[2]
        self.assertEqual(json.loads(values["recipients"]), ["opted-in"])

    def test_admin_guard_precedes_mutation(self):
        self.scope.require_platform.side_effect = PermissionError
        for fn, args in [(self.service.send, ("campaign",)), (self.service.cancel, ("campaign",)),
                         (self.service.test, ("campaign",)), (self.service.save, ("shop", "title", "body"))]:
            with self.assertRaises(PermissionError):
                fn(*args)
        self.frappe.db.set_value.assert_not_called()
        self.service._notify.assert_not_called()

    def test_disabled_or_opted_out_users_not_allowed(self):
        for values in ([0], [1, 0]):
            self.frappe.db.get_value.side_effect = values
            self.assertFalse(self.service.allowed("customer"))

    def test_push_permission_includes_promotions_without_separate_preference(self):
        self.frappe.db.get_value.return_value = None
        self.frappe.db.exists.return_value = True
        self.assertTrue(self.service.promotion_enabled("customer"))

    def test_explicit_opt_out_overrides_active_push(self):
        self.frappe.db.get_value.return_value = 0
        self.frappe.db.exists.return_value = True
        self.assertFalse(self.service.promotion_enabled("customer"))
        self.frappe.db.exists.assert_not_called()

    def test_no_push_and_no_preference_is_not_opted_in(self):
        self.frappe.db.get_value.return_value = None
        self.frappe.db.exists.return_value = False
        self.assertFalse(self.service.promotion_enabled("customer"))

    def test_wording_history_scopes_product_and_shop(self):
        self.service.wording_history("shop", "eggs")
        self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"], {"shop": "shop", "item": "eggs"})
        self.service.wording_history("shop")
        self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"], {"shop": "shop", "item": ["is", "not set"]})
        self.scope.require_platform.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.service.wording_history("shop")

    def test_automatic_cap_and_spacing(self):
        from datetime import timedelta
        for count, elapsed, expected in [(0, None, True), (4, 150, True), (4, 149, False), (5, 180, False)]:
            self.frappe.db.sql.return_value = [SimpleNamespace(today_count=count,
                last_sent=self.now - timedelta(minutes=elapsed) if elapsed is not None else None)]
            self.assertEqual(self.service.automatic_due("customer", self.now), expected)

    def test_previous_day_message_still_requires_spacing(self):
        self.frappe.db.sql.return_value = [SimpleNamespace(today_count=0, last_sent=datetime(2026, 10, 29, 23, 30))]
        self.assertFalse(self.service.automatic_due("customer", datetime(2026, 10, 30, 0, 30)))

    def test_daily_copy_rotates_and_respects_category(self):
        product = {"item_name": "Bangde Pack", "item_group": "Fish & Seafood"}
        ideas = [self.service.daily_wording(product, "Daily Basket", day) for day in range(5)]
        self.assertEqual(len(set(title for title, _ in ideas)), 5)
        self.assertTrue(all("Bangde Pack at Daily Basket" in body for _, body in ideas))
        title, _ = self.service.daily_wording({"item_name": "Eggs", "item_group": "Dairy & Eggs"}, "Fish Market", 0)
        self.assertIn("Breakfast", title)

    def test_automatic_copy_has_one_hundred_distinct_messages(self):
        for category in ("Fish", "Dairy", "Vegetables", "Meat", "Bakery", "Beverages", "Groceries", "Household"):
            product = {"item_name": "Selected product", "item_group": category}
            ideas = [self.service.daily_wording(product, "Shop", index) for index in range(100)]
            self.assertEqual(len(set(body for _, body in ideas)), 100)
            self.assertEqual(len(set(title for title, _ in ideas)), 100)
            self.assertTrue(all(len(title) <= 80 and len(body) <= 240 for title, body in ideas))
            self.assertEqual(self.service.daily_wording(product, "Shop", 100), ideas[0])

    def test_batch_stops_if_shop_closes(self):
        self.service.shop_is_open.side_effect = [True, False]
        self.service.process_one("campaign")
        self.service._notify.assert_not_called()
        self.assertEqual(self.frappe.db.set_value.call_args.args[2]["cursor"], 0)

    def test_daily_scheduler_sends_once_and_skips_already_notified(self):
        product = {"item_name": "Bangde", "item_group": "Fish", "available": 5, "rate": 10}
        self.service._lock = Mock(return_value=self.doc)
        self.doc.item = "fish"
        self.doc.status = "Completed"
        self.service.allowed = Mock(return_value=True)
        self.service.automatic_due = Mock(side_effect=[True, False])
        self.frappe.db.get_value.return_value = "campaign"
        with patch.dict(sys.modules, {
            "local_commerce.services.orders": SimpleNamespace(public_product=Mock(return_value=product)),
            "local_commerce.services.stock_alerts": SimpleNamespace(restocked=lambda value: value["available"] > 0),
        }):
            for _ in range(2):
                self.frappe.get_all.side_effect = [["shop"], ["fish"], ["customer"], ["customer"]]
                self.service.process_daily()
        self.service._notify.assert_called_once_with(self.doc, "customer")

    def test_daily_scheduler_does_not_choose_closed_shop(self):
        self.service.shop_is_open.return_value = False
        self.frappe.get_all.return_value = ["shop"]
        with patch.dict(sys.modules, {
            "local_commerce.services.orders": SimpleNamespace(public_product=Mock()),
            "local_commerce.services.stock_alerts": SimpleNamespace(restocked=Mock()),
        }):
            self.service.process_daily()
        self.service._notify.assert_not_called()
        self.frappe.get_all.assert_called_once()

    def test_guest_cannot_change_consent(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.service.preference(1)
        self.frappe.db.set_value.assert_not_called()

    def test_batch_preserves_progress(self):
        self.doc.recipients = json.dumps([str(i) for i in range(105)])
        self.doc.cursor = 100
        self.doc.queued_count = 100
        self.service.allowed = Mock(return_value=True)
        self.frappe.db.count.return_value = 0
        self.service.process_one("campaign")
        self.assertEqual(self.service._notify.call_count, 5)
        self.assertEqual(self.frappe.db.set_value.call_args.args[2]["queued_count"], 105)

    def test_goan_library_has_exactly_50_bilingual_unique_pairs(self):
        rows = self.templates.library()
        from collections import Counter
        self.assertEqual(len(rows), 50)
        self.assertEqual(len({r['id'] for r in rows}), 50)
        self.assertEqual(sorted(Counter(r['category'] for r in rows).values()), [5, 10, 15, 20])
        for script in ('latin', 'devanagari'):
            self.assertEqual(len({r[script]['title'] for r in rows}), 50)
            self.assertEqual(len({r[script]['message'] for r in rows}), 50)
            for row in rows:
                self.assertLessEqual(len(row[script]['title']), 80)
                self.assertLessEqual(len(row[script]['message']), 120)
        self.assertNotIn('polle', json.dumps(rows))

    def test_goan_fish_mapping_is_explicit_not_a_name_guess(self):
        config = self.templates.validate_settings({'fish_tags': {'eggs': 'fish', 'fish': 'bangde'}})
        bangde = self.templates.template('goan-01')
        self.assertTrue(self.templates.matches(bangde, 'fish', config))
        self.assertFalse(self.templates.matches(bangde, 'eggs', config))
        self.assertFalse(self.templates.matches(bangde, 'Bangde Pack', config))

    def test_goan_weekend_and_time_boundaries(self):
        config = self.templates.validate_settings({})
        sunday = self.templates.template('goan-47')
        self.assertFalse(self.templates.time_allowed(sunday, datetime(2026, 11, 7, 12), config))
        self.assertTrue(self.templates.time_allowed(sunday, datetime(2026, 11, 8, 12), config))
        self.assertFalse(self.templates.time_allowed(sunday, datetime(2026, 11, 8, 14), config))
        generic = self.templates.template('goan-05')
        self.assertFalse(self.templates.time_allowed(generic, datetime(2026, 11, 8, 7, 59), config))
        self.assertTrue(self.templates.time_allowed(generic, datetime(2026, 11, 8, 8), config))
        self.assertFalse(self.templates.time_allowed(generic, datetime(2026, 11, 8, 19), config))

    def test_goan_settings_validate_and_require_admin(self):
        for value in ({'disabled': ['bad']}, {'fish_tags': {'x': []}}, {'start': 19, 'end': 8}, {'script': 'other'}, {'automatic': 'false'}):
            with self.assertRaises(ValueError):
                self.templates.validate_settings(value)
        self.scope.require_platform.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.templates.configure({})
        self.frappe.db.set_single_value.assert_not_called()

    def test_goan_disabled_and_wrong_product_rejected(self):
        self.frappe.db.get_single_value.return_value = json.dumps({'fish_tags': {'fish': 'bangde'}, 'disabled': ['goan-01']})
        with self.assertRaises(ValueError):
            self.templates.validate_campaign('goan-01', 'latin', 'fish', 'All', '')
        with self.assertRaises(ValueError):
            self.templates.validate_campaign('goan-02', 'latin', 'fish', 'All', '')
        self.templates.validate_campaign('goan-05', 'devanagari', 'fish', 'All', '')

    def test_delivery_rechecks_sold_out_product_and_template_disable(self):
        self.doc.item = 'fish'
        self.doc.template_id = 'goan-01'
        self.frappe.db.get_single_value.return_value = json.dumps({'fish_tags': {'fish': 'bangde'}})
        stock = Mock(return_value=False)
        with patch.dict(sys.modules, {
            'local_commerce.services.orders': SimpleNamespace(public_product=Mock(return_value={})),
            'local_commerce.services.stock_alerts': SimpleNamespace(restocked=stock),
        }):
            self.assertEqual(self.templates.delivery_state(self.doc), 'Product unavailable')
            stock.return_value = True
            self.assertEqual(self.templates.delivery_state(self.doc), 'ready')
            self.frappe.db.get_single_value.return_value = json.dumps({'disabled': ['goan-01'], 'fish_tags': {'fish': 'bangde'}})
            self.assertEqual(self.templates.delivery_state(self.doc), 'Template disabled')

    def test_shop_audience_intersects_consent_snapshot(self):
        self.doc.status = 'Draft'
        self.doc.campaign_audience = 'Shop customers'
        self.service.allowed = lambda account: account != 'opted-out'
        self.frappe.get_all.side_effect = [['customer', 'outsider', 'opted-out'], [], ['customer', 'opted-out']]
        self.service.send('campaign')
        self.assertEqual(json.loads(self.frappe.db.set_value.call_args.args[2]['recipients']), ['customer'])

    def test_automatic_goan_is_off_by_default_and_avoids_last_template(self):
        self.assertIsNone(self.templates.automatic_choice('shop', 'fish', self.now))
        self.frappe.db.get_single_value.return_value = json.dumps({'automatic': True, 'fish_tags': {'fish': 'bangde'}, 'script': 'devanagari'})
        self.frappe.get_all.return_value = [{'template_id': 'goan-01'}]
        choice = self.templates.automatic_choice('shop', 'fish', self.now)
        self.assertNotEqual(choice['template_id'], 'goan-01')
        self.assertEqual(choice['template_script'], 'devanagari')

    def test_manual_sold_out_campaign_is_skipped(self):
        self.doc.item = 'fish'
        with patch.dict(sys.modules, {
            'local_commerce.services.orders': SimpleNamespace(public_product=Mock(return_value={})),
            'local_commerce.services.stock_alerts': SimpleNamespace(restocked=lambda product: False),
        }):
            self.service.process_one('campaign')
        self.service._notify.assert_not_called()
        self.assertEqual(self.frappe.db.set_value.call_args.args[2]['skipped_count'], 3)


    def test_duplicate_campaign_recipient_is_not_inserted_again(self):
        self.frappe.db.exists.return_value = True
        self.frappe.get_doc.reset_mock()
        self.assertFalse(self.original_notify(self.doc, 'customer'))
        self.frappe.get_doc.assert_not_called()
        self.frappe.enqueue.assert_not_called()

    def test_push_worker_suppresses_unavailable_and_defers_time_window(self):
        spec = importlib.util.spec_from_file_location('push_test', Path('local_commerce/services/push.py'))
        push = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(push)
        push._private_key_path = Mock(return_value=SimpleNamespace(is_file=lambda: True))
        row = SimpleNamespace(campaign='campaign', campaign_test=0, campaign_push_state='Pending',
                              creation=self.now, shop='shop', recipient_user='customer')
        row.get = lambda key: getattr(row, key, None)
        self.service.allowed = Mock(return_value=True)
        with patch.dict(sys.modules, {'local_commerce.services.campaigns': self.service}):
            for state in ('Product unavailable', 'wait', 'Template disabled'):
                self.frappe.db.set_value.reset_mock()
                self.frappe.db.get_value.side_effect = [row, 'Completed']
                with patch.object(self.templates, 'delivery_state', return_value=state):
                    push.send_notification('notification')
                if state == 'wait':
                    self.frappe.db.set_value.assert_not_called()
                else:
                    self.assertEqual(self.frappe.db.set_value.call_args.args[2]['campaign_suppression_reason'], state)
        self.frappe.get_all.assert_not_called()

if __name__ == "__main__":
    unittest.main()
