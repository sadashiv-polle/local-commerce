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
