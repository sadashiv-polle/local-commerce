import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class Row(dict):
    __getattr__ = dict.get


class HomeDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.frappe, self.orders, self.customers = Mock(), Mock(), Mock()
        owner = Mock()
        owner.reject.side_effect = ValueError
        self.scope = patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "frappe.utils": SimpleNamespace(now_datetime=lambda: "now"),
                "local_commerce.services.owner": owner,
            },
        )
        self.frappe.get_single.return_value = Row(pinned_shop="")
        self.scope.start()
        self.addCleanup(self.scope.stop)
        spec = importlib.util.spec_from_file_location(
            "home_under_test", Path("local_commerce/services/home_discovery.py")
        )
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        import local_commerce.services as services

        for name, value in [("orders", self.orders), ("customers", self.customers)]:
            scoped = patch.object(services, name, value, create=True)
            scoped.start()
            self.addCleanup(scoped.stop)
        self.orders.shops.return_value = [Row(name="fish", accepting_orders=True)]
        self.frappe.get_all.return_value = [
            Row(
                name="fish",
                shop_image="/private/files/secret.jpg",
                shop_type="Fish",
                company_currency="INR",
                minimum_order_amount=100,
                free_delivery_above=350,
                delivery_enabled=1,
                scheduled_enabled=1,
            )
        ]
        self.frappe.db.sql.return_value = [
            Row(
                shop="fish",
                title="Morning",
                ordering_start="opens",
                ordering_end="cutoff",
                delivery_start="start",
                delivery_end="end",
            )
        ]

    def test_public_cards_hide_private_images_and_include_existing_configuration(self):
        result = self.service.discover("Fish", "", 20)
        self.orders.shops.assert_called_once_with(20, "Fish", pinned_shop="")
        row = result["shops"][0]
        self.assertEqual(row["shop_image"], "")
        self.assertEqual(row["minimum_order_amount"], 100)
        self.assertEqual(row["next_slot"]["ordering_end"], "cutoff")
        self.assertNotIn("shop", row["next_slot"])
        query, args = self.frappe.db.sql.call_args.args
        self.assertIn("s.enabled=1", query)
        self.assertIn("o.status!='Cancelled'", query)
        self.assertIn("s.capacity", query)
        self.assertEqual(args, ("fish", "now"))

    def test_stored_shop_id_is_never_interpolated_into_slot_sql(self):
        payload = "shop') OR 1=1 --"
        self.orders.shops.return_value[0]["name"] = payload
        self.frappe.get_all.return_value[0]["name"] = payload
        self.service.discover()
        query, values = self.frappe.db.sql.call_args.args
        self.assertNotIn(payload, query)
        self.assertEqual(values[0], payload)

    def test_selected_address_uses_existing_ownership_check(self):
        self.customers.nearby.side_effect = PermissionError("foreign address")
        with self.assertRaises(PermissionError):
            self.service.discover("", "foreign", 0)
        self.customers.nearby.assert_called_once_with("foreign", 0, "", pinned_shop="")
        self.orders.shops.assert_not_called()
        self.frappe.get_all.assert_not_called()

    def test_search_keeps_active_shop_scope_and_escapes_wildcards(self):
        result = self.service.search_filters("  50%_fish  ")
        self.assertEqual(result["status"], "Active")
        self.assertEqual(result["shop_name"], ["like", "%50\\%\\_fish%"])
        with self.assertRaises(ValueError):
            self.service.search_filters("x" * 141)

    def test_empty_results_skip_metadata_and_slot_queries(self):
        self.orders.shops.return_value = []
        self.assertEqual(self.service.discover(), {"shops": [], "has_more": False})
        self.frappe.db.sql.assert_not_called()

    def test_priority_passed_to_discovery(self):
        self.frappe.get_single.return_value = Row(pinned_shop="fish")
        self.service.discover()
        self.orders.shops.assert_called_once_with(0, "", pinned_shop="fish")
