import unittest

from local_commerce.permissions.policy import can_manage_schedule


class TestSchedulePermissions(unittest.TestCase):
    def test_extra_role_is_scoped_to_enabled_owned_shop(self):
        owner = {"user": "owner", "shop": "own", "membership_role": "Owner", "enabled": 1}
        roles = ["LC Shop Owner", "LC Scheduled Delivery Manager"]
        self.assertTrue(can_manage_schedule("owner", roles, [owner], "own"))
        self.assertFalse(can_manage_schedule("owner", roles, [owner], "other"))
        self.assertFalse(can_manage_schedule("owner", ["LC Shop Owner"], [owner], "own"))
        self.assertFalse(can_manage_schedule("owner", roles, [{**owner, "enabled": 0}], "own"))
        self.assertFalse(can_manage_schedule("owner", roles, [], "own"))
        self.assertFalse(can_manage_schedule("Guest", roles, [owner], "own"))
        self.assertTrue(can_manage_schedule("Administrator", [], [], "own"))
