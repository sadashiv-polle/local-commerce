import importlib.util
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class UsernameTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        with patch.dict(
            sys.modules,
            {
                "frappe": self.frappe,
                "local_commerce.services.owner": SimpleNamespace(
                    reject=Mock(side_effect=ValueError)
                ),
            },
        ):
            spec = importlib.util.spec_from_file_location(
                "username_test", "local_commerce/services/usernames.py"
            )
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

    def test_first_name_only(self):
        self.frappe.db.sql.side_effect = [[("Administrator",)], []]
        self.assertEqual(self.module.allocate(" Aditya Polle "), "aditya")

    def test_taken_username_gets_random_suffix_and_retries_collisions(self):
        self.frappe.db.sql.side_effect = [[("Administrator",)], [("existing",)], [("taken",)], []]
        with patch.object(self.module.secrets, "randbelow", side_effect=[382, 639]):
            self.assertEqual(self.module.allocate("Aditya Polle"), "aditya739")
        self.assertEqual(self.frappe.db.sql.call_args.args[1], ("aditya739", "aditya739"))

    def test_names_are_normalized_and_bounded(self):
        self.assertEqual(self.module.first_name_base("ADITYA Polle"), "aditya")
        self.assertEqual(self.module.first_name_base("---"), "user")
        self.assertEqual(len(self.module.first_name_base("a" * 200)), 40)

    def test_exhaustion_fails_without_reusing_username(self):
        self.frappe.db.sql.return_value = [("taken",)]
        with self.assertRaises(ValueError):
            self.module.allocate("aditya")
