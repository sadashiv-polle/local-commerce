import ast
import json
import unittest
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import Mock


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.doc = Mock()
        self.doc.name = 'one-order'
        self.doc.shop = 'shop'
        self.doc.status = 'Ready'
        self.doc.delivery_user = 'old-rider'
        self.doc.assigned_at = 'yesterday'
        self.doc.get.return_value = '[]'
        self.frappe = Mock()
        self.frappe.get_doc.return_value = self.doc
        self.frappe.session.user = 'owner'
        self.frappe.db.get_value.return_value = 'Rider'
        def reject(message):
            raise ValueError(message)
        scope = dict(frappe=self.frappe, authorize=Mock(), reject=reject, is_shop_driver=lambda *a: True,
                     _order_operation=ContextVar('test', default=False), now_datetime=lambda: 'now',
                     json=json, serialize=lambda doc: doc.name, escape=lambda s: s, order_notifications=Mock())
        tree = ast.parse(Path('local_commerce/services/orders.py').read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'assign_driver']
        exec(compile(tree, 'orders.py', 'exec'), scope)
        self.assign = scope['assign_driver']

    def test_unassign_records_actor_and_preserves_previous_assignment(self):
        self.assign('one-order', '')
        self.assertIsNone(self.doc.delivery_user)
        self.assertIsNone(self.doc.assigned_at)
        history = json.loads(self.doc.assignment_history_json)
        self.assertEqual(history[0]['by'], 'Not recorded')
        self.assertEqual(history[-1], {'action': 'Unassigned', 'rider': 'old-rider', 'by': 'owner', 'at': 'now'})
        self.frappe.get_doc.assert_called_once_with('LC Order', 'one-order')

    def test_pickup_blocks_unassignment(self):
        self.doc.status = 'Picked Up'
        with self.assertRaises(ValueError):
            self.assign('one-order', '')
        self.doc.save.assert_not_called()

    def test_assignment_records_new_rider(self):
        self.assign('one-order', 'new-rider')
        self.assertEqual(self.doc.delivery_user, 'new-rider')
        self.assertEqual(json.loads(self.doc.assignment_history_json)[-1]['action'], 'Reassigned')
