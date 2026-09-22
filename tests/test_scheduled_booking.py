import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class Doc(SimpleNamespace):
    def get(self, field):
        return getattr(self, field, None)


class TestScheduledBooking(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.db.count.return_value = 0
        self.owner = Mock()
        self.owner.reject.side_effect = ValueError
        self.scope = Mock()
        modules = patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "frappe.utils": SimpleNamespace(
                    get_datetime=lambda v: datetime.fromisoformat(str(v)),
                    now_datetime=lambda: datetime(2026, 9, 21, 8),
                ),
                "local_commerce.services.owner": self.owner,
                "local_commerce.permissions.scope": self.scope,
            },
        )
        modules.start()
        self.addCleanup(modules.stop)
        spec = importlib.util.spec_from_file_location(
            "scheduled_under_test",
            Path(__file__).resolve().parents[1] / "local_commerce/services/scheduled.py",
        )
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.shop = Doc(name="shop", delivery_enabled=1, scheduled_enabled=1)
        self.slot = Doc(
            name="slot",
            shop="shop",
            enabled=1,
            ordering_start="2026-09-21 07:00",
            ordering_end="2026-09-21 09:00",
            capacity=20,
            products="item",
        )
        self.frappe.get_doc.return_value = self.slot

    def test_four_mode_combinations(self):
        for normal in (0, 1):
            for scheduled in (0, 1):
                self.shop.delivery_enabled = normal
                self.shop.scheduled_enabled = scheduled
                for mode, enabled in [("Normal", normal), ("Scheduled", scheduled)]:
                    if enabled:
                        self.service.validate_booking(self.shop, mode, "slot", [{"item": "item"}])
                    else:
                        with self.assertRaises(ValueError):
                            self.service.validate_booking(
                                self.shop, mode, "slot", [{"item": "item"}]
                            )

    def test_closed_full_wrong_shop_and_product(self):
        for key, value in [
            ("enabled", 0),
            ("shop", "other"),
            ("ordering_end", "2026-09-21 08:00"),
            ("ordering_start", "2026-09-21 09:00"),
            ("products", "other"),
        ]:
            old = getattr(self.slot, key)
            setattr(self.slot, key, value)
            with self.assertRaises(ValueError):
                self.service.validate_booking(self.shop, "Scheduled", "slot", [{"item": "item"}])
            setattr(self.slot, key, old)
        self.frappe.db.count.return_value = 20
        with self.assertRaises(ValueError):
            self.service.validate_booking(self.shop, "Scheduled", "slot", [{"item": "item"}])

    def test_admin_required_before_configuration(self):
        self.scope.require_platform.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.service.configure("shop", 1, 1)
        self.frappe.get_doc.assert_not_called()

    def test_address_zone_and_radius(self):
        from local_commerce.services.location_rules import point

        self.slot.radius_km = 5
        self.slot.postcodes = "403001"
        with patch.dict(
            sys.modules,
            {
                "local_commerce.services.locations": SimpleNamespace(
                    shop_location=lambda doc: point(15.49, 73.82)
                )
            },
        ):
            address = {"latitude": 15.49, "longitude": 73.82, "postal_code": "403001"}
            self.assertIs(
                self.service.validate_booking(
                    self.shop, "Scheduled", "slot", [{"item": "item"}], address
                ),
                self.slot,
            )
            for changed in [{**address, "postal_code": "999999"}, {**address, "latitude": 17}]:
                with self.assertRaises(ValueError):
                    self.service.validate_booking(
                        self.shop, "Scheduled", "slot", [{"item": "item"}], changed
                    )

    def test_batch_rolls_back_when_one_order_fails(self):
        import local_commerce.services as services

        orders = Mock()
        orders.change.side_effect = [None, ValueError("Stock expired")]
        self.service.batch = Mock(
            return_value=(
                self.slot,
                [{"name": "a", "status": "Preparing"}, {"name": "b", "status": "Preparing"}],
            )
        )
        with patch.object(services, "orders", orders, create=True):
            with self.assertRaisesRegex(ValueError, "Stock expired"):
                self.service.advance_batch("slot", "Ready")
        self.frappe.db.rollback.assert_called_once_with(save_point="lc_batch_transition")
        self.assertEqual(orders.change.call_count, 2)
        self.scope.require_shop.assert_called_with("shop", "write")

    def test_batch_retry_skips_orders_already_advanced(self):
        import local_commerce.services as services

        orders = Mock()
        self.service.batch = Mock(
            return_value=(
                self.slot,
                [{"name": "a", "status": "Preparing"}, {"name": "b", "status": "Ready"}],
            )
        )
        with patch.object(services, "orders", orders, create=True):
            result = self.service.advance_batch("slot", "Preparing")
        self.assertEqual(result["changed"], 0)
        orders.change.assert_not_called()
        self.frappe.db.rollback.assert_not_called()

    def test_batch_pickup_requires_assigned_delivery_person(self):
        import local_commerce.services as services
        orders = Mock()
        orders.is_shop_driver.return_value = False
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = PermissionError
        with patch.object(services, 'orders', orders, create=True):
            with self.assertRaises(PermissionError):
                self.service.advance_batch('slot', 'Picked Up')
        orders.delivery_change.assert_not_called()

    def test_admin_history_keeps_past_and_hidden_slots_with_pagination(self):
        self.frappe.get_all.return_value = []
        self.service.slots('shop', admin=True, start=100)
        kwargs = self.frappe.get_all.call_args.kwargs
        self.assertEqual(kwargs['filters'], {'shop': 'shop'})
        self.assertEqual(kwargs['start'], 100)
        self.scope.require_shop.assert_called_with('shop')

    def test_customers_only_see_enabled_future_slots(self):
        self.shop.status = 'Active'
        self.frappe.get_doc.return_value = self.shop
        self.frappe.get_all.return_value = []
        self.service.slots('shop')
        kwargs = self.frappe.get_all.call_args.kwargs
        self.assertEqual(kwargs['filters']['enabled'], 1)
        self.assertIn('delivery_end', kwargs['filters'])
        self.assertEqual(kwargs['start'], 0)
