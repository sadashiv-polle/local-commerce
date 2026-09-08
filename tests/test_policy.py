import unittest

from local_commerce.permissions.policy import can_access_shop


class PermissionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.user = "owner@example.test"
        self.roles = ["LC Shop Owner"]
        self.members = [{"shop": "A", "user": self.user, "membership_role": "Owner", "enabled": 1}]

    def test_owner_only_reads_and_writes_own_shop(self):
        self.assertTrue(can_access_shop(self.user, self.roles, self.members, "A"))
        self.assertTrue(can_access_shop(self.user, self.roles, self.members, "A", "write"))
        for operation in ("read", "write", "delete", "create", "export"):
            self.assertFalse(can_access_shop(self.user, self.roles, self.members, "B", operation))
        self.assertFalse(can_access_shop(self.user, self.roles, self.members, "A", "delete"))

    def test_membership_without_role_denied(self):
        self.assertFalse(can_access_shop(self.user, [], self.members, "A"))

    def test_disabled_membership_denied(self):
        self.members[0]["enabled"] = 0
        self.assertFalse(can_access_shop(self.user, self.roles, self.members, "A"))

    def test_other_user_membership_denied(self):
        self.assertFalse(can_access_shop("other@example.test", self.roles, self.members, "A"))

    def test_staff_read_only(self):
        self.members[0]["membership_role"] = "Staff"
        roles = ["LC Shop Staff"]
        self.assertTrue(can_access_shop(self.user, roles, self.members, "A"))
        self.assertFalse(can_access_shop(self.user, roles, self.members, "A", "write"))

    def test_driver_and_customer_cannot_manage_shops(self):
        self.members[0]["membership_role"] = "Driver"
        for role in ("LC Delivery Person", "LC Customer"):
            self.assertFalse(can_access_shop(self.user, [role], self.members, "A"))

    def test_guest_is_always_denied(self):
        self.assertFalse(can_access_shop("Guest", ["LC Platform Administrator"], [], "A"))

    def test_platform_and_builtin_administrator(self):
        self.assertTrue(can_access_shop(self.user, ["LC Platform Administrator"], [], "B", "write"))
        self.assertTrue(can_access_shop("Administrator", [], [], "B", "delete"))

    def test_system_manager_is_not_implicitly_platform(self):
        self.assertFalse(can_access_shop(self.user, ["System Manager"], [], "A"))
