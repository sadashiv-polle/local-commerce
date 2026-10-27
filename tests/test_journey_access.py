import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class JourneyAccessTests(unittest.TestCase):
    def run_route(self, user, status, member=True):
        source = Path('local_commerce/services/orders.py').read_text()
        function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'journey_route')
        doc = SimpleNamespace(delivery_user=user, status=status, shop='shop-a')
        def reject(message):
            raise ValueError(message)
        scope = {'frappe': SimpleNamespace(get_doc=Mock(return_value=doc), session=SimpleNamespace(user='rider-a')),
                 'is_shop_driver': Mock(return_value=member), 'reject': reject}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<journey>', 'exec'), scope)
        scope['journey_route']('order-a', 15, 73)

    def test_other_rider_cannot_route_order(self):
        with self.assertRaisesRegex(ValueError, 'assigned rider'):
            self.run_route('rider-b', 'Ready')

    def test_disabled_membership_cannot_route(self):
        with self.assertRaisesRegex(ValueError, 'assigned rider'):
            self.run_route('rider-a', 'Ready', False)

    def test_completed_order_cannot_route(self):
        with self.assertRaisesRegex(ValueError, 'no longer active'):
            self.run_route('rider-a', 'Delivered')
