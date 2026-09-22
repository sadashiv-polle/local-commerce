import importlib.util
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from local_commerce.services.schedule_rules import daily_window


class Doc(SimpleNamespace):
    def get(self, field):
        return getattr(self, field, None)

    def update(self, values):
        self.__dict__.update(values)


class TestDailyWindow(unittest.TestCase):
    def test_times_and_midnight(self):
        values = daily_window(date(2026, 9, 22), ['07:00', '09:00', '10:00', '00:00'])
        self.assertEqual(values[-1], datetime(2026, 9, 23))
        self.assertEqual(daily_window(date(2026, 9, 22), [
            timedelta(hours=h) for h in (7, 9, 10, 11)
        ])[0], datetime(2026, 9, 22, 7))

    def test_delivery_before_ordering_closes_is_rejected(self):
        with self.assertRaises(ValueError):
            daily_window(date(2026, 9, 22), ['07:00', '10:00', '09:00', '11:00'])


class TestDailyGeneration(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        modules = patch.dict(sys.modules, {
            'frappe': self.frappe,
            'frappe.utils': SimpleNamespace(now_datetime=lambda: datetime(2026, 9, 22, 6)),
            'local_commerce.permissions.scope': Mock(),
            'local_commerce.services.owner': Mock(),
        })
        modules.start()
        self.addCleanup(modules.stop)
        spec = importlib.util.spec_from_file_location('daily_under_test', Path(__file__).resolve(
        ).parents[1] / 'local_commerce/services/recurring_delivery.py')
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.schedule = Doc(name='morning', shop='shop', title='Morning', enabled=1,
                            ordering_start='07:00', ordering_end='09:00',
                            delivery_start='10:00', delivery_end='12:00', capacity=20,
                            products='', postcodes='', radius_km=5)
        self.slots = {}
        self.booked = set()
        self.frappe.db.exists.side_effect = lambda dt, value: (
            value in self.slots if dt == 'LC Delivery Slot'
            else value['scheduled_slot'] in self.booked
        )
        self.frappe.get_doc.side_effect = lambda dt, name: (
            self.schedule if dt == 'LC Delivery Schedule' else self.slots[name]
        )
        def new_doc(dt):
            doc = Doc(flags=SimpleNamespace(), save=Mock())
            def insert(**kwargs):
                self.slots[kwargs['set_name']] = doc
            doc.insert = Mock(side_effect=insert)
            return doc
        self.frappe.new_doc.side_effect = new_doc

    def test_daily_batches_idempotent_and_distinct(self):
        self.service.sync_schedule(self.schedule)
        self.service.sync_schedule(self.schedule)
        self.assertEqual(len(self.slots), 2)
        today = self.slots['daily-morning-2026-09-22']
        tomorrow = self.slots['daily-morning-2026-09-23']
        self.assertNotEqual(today.ordering_start, tomorrow.ordering_start)
        today.save.assert_not_called()
        tomorrow.save.assert_not_called()

    def test_booked_dates_keep_commitments_but_can_be_hidden(self):
        self.service.sync_schedule(self.schedule)
        identity = 'daily-morning-2026-09-22'
        today = self.slots[identity]
        self.booked.add(identity)
        self.schedule.delivery_start = '11:00'
        self.schedule.capacity = 25
        self.schedule.enabled = 0
        self.service.sync_schedule(self.schedule)
        self.assertEqual(today.delivery_start.hour, 10)
        self.assertEqual(today.capacity, 20)
        self.assertEqual(today.enabled, 0)
        tomorrow = self.slots['daily-morning-2026-09-23']
        self.assertEqual(tomorrow.delivery_start.hour, 11)
        self.assertEqual(tomorrow.capacity, 25)
        self.assertEqual(tomorrow.enabled, 0)

    def test_deleting_schedule_retains_booked_batches_and_removes_empty_ones(self):
        self.frappe.get_all.return_value = ['booked', 'empty']
        self.booked.add('booked')
        self.service.cleanup_schedule(self.schedule)
        self.frappe.db.set_value.assert_called_once_with(
            'LC Delivery Slot', 'booked', {'daily_schedule': None, 'enabled': 0}
        )
        self.frappe.delete_doc.assert_called_once_with(
            'LC Delivery Slot', 'empty', ignore_permissions=True
        )
