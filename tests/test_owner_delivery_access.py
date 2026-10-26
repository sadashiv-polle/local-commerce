import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class OwnerDeliveryAccessTests(TestCase):
    def allowed(self, user, shop, roles, membership):
        tree = ast.parse(Path('local_commerce/services/orders.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'is_shop_driver']
        db = Mock()
        db.exists.side_effect = lambda doctype, filters: all(membership.get(k) == v for k, v in filters.items())
        scope = {'frappe': SimpleNamespace(get_roles=lambda user: roles, db=db)}
        exec(compile(tree, 'orders', 'exec'), scope)
        return scope['is_shop_driver'](user, shop)

    def test_owner_can_deliver_only_in_own_enabled_shop(self):
        member = dict(user='owner', shop='A', membership_role='Owner', enabled=1)
        self.assertTrue(self.allowed('owner', 'A', ['LC Shop Owner'], member))
        self.assertFalse(self.allowed('owner', 'B', ['LC Shop Owner'], member))
        self.assertFalse(self.allowed('owner', 'A', [], member))
        self.assertFalse(self.allowed('owner', 'A', ['LC Shop Owner'], {**member, 'enabled': 0}))

    def test_staff_cannot_deliver_and_rider_still_can(self):
        member = dict(user='rider', shop='A', membership_role='Delivery Person', enabled=1)
        self.assertTrue(self.allowed('rider', 'A', ['LC Delivery Person'], member))
        self.assertFalse(self.allowed('rider', 'A', ['LC Shop Staff'], {**member, 'membership_role': 'Staff'}))
        self.assertFalse(self.allowed('Guest', 'A', ['LC Shop Owner'], member))
