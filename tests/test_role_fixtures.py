"""Regression coverage for Frappe's named-document fixture import contract."""

import json
import unittest
from pathlib import Path

from local_commerce.permissions.policy import MEMBER_ROLES, PLATFORM_ROLE


class RoleFixtureTests(unittest.TestCase):
    def test_roles_have_unique_import_names_matching_permission_roles(self):
        path = Path(__file__).resolve().parents[1] / "local_commerce/fixtures/role.json"
        records = json.loads(path.read_text())
        names = [record["name"] for record in records]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), {PLATFORM_ROLE, *MEMBER_ROLES.values(), "LC Customer"})
        for record in records:
            self.assertEqual(record["doctype"], "Role")
            self.assertEqual(record["name"], record["role_name"])
