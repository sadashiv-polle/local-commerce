import importlib.util
import json
import sys
import unittest
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class Doc(SimpleNamespace):
    def get(self, key):
        return getattr(self, key, None)


class ManualUpiTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.session.user = 'payer'
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = lambda message, kind: (_ for _ in ()).throw(kind(message))
        self.scope = Mock()
        self.owner = Mock()
        self.owner.reject.side_effect = lambda message: (_ for _ in ()).throw(ValueError(message))
        self.owner._owner_operation = ContextVar('owner_test', default=False)
        self.orders = Mock()
        self.orders._order_operation = ContextVar('order_test', default=False)
        self.patch = patch.dict(sys.modules, {
            'frappe': self.frappe, 'frappe.utils': Mock(),
            'local_commerce.permissions.scope': self.scope,
            'local_commerce.services.owner': self.owner,
            'local_commerce.services.orders': self.orders,
            'local_commerce.services.notifications': Mock(),
        })
        self.patch.start()
        self.addCleanup(self.patch.stop)
        spec = importlib.util.spec_from_file_location('upi_test', Path(__file__).resolve(
        ).parents[1] / 'local_commerce/services/manual_upi.py')
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.doc = Doc(name='order', shop='shop', customer_user='payer',
                       payment_method='Manual UPI', payment_status='Pending', status='Accepted',
                       selling_lines_json='[]', upi_bank_account='bank',
                       save=Mock(), reload=Mock(), add_comment=Mock())
        self.frappe.get_doc.return_value = self.doc

    def test_payment_only_after_acceptance_and_final_weights(self):
        for status in ['Requested', 'Cancelled', 'Delivered', 'Out for Delivery']:
            self.doc.status = status
            self.assertFalse(self.service.payable(self.doc))
        self.doc.status = 'Accepted'
        self.doc.selling_lines_json = json.dumps([{'option_id': 'kg', 'actual_weight': None}])
        self.assertFalse(self.service.payable(self.doc))
        self.doc.selling_lines_json = json.dumps([{'option_id': 'kg', 'actual_weight': .53}])
        self.assertTrue(self.service.payable(self.doc))

    def test_another_customer_cannot_upload(self):
        self.frappe.session.user = 'other'
        with self.assertRaises(PermissionError):
            self.service.upload_proof('order')
        self.doc.save.assert_not_called()

    def test_upload_is_pending_never_paid(self):
        self.service.save_image = Mock(return_value='/private/files/proof.jpg')
        self.service.upload_proof('order')
        self.assertEqual(self.doc.payment_status, 'Awaiting Verification')
        self.service.save_image.assert_called_once_with('LC Order', 'order', True)
        self.assertFalse(self.orders._order_operation.get())
        with self.assertRaises(ValueError):
            self.service.upload_proof('order')

    def test_reject_requires_reason_and_allows_new_proof(self):
        self.doc.payment_status = 'Awaiting Verification'
        with self.assertRaises(ValueError):
            self.service.review('order', approve=False)
        self.service.review('order', approve=False, note='Credit not found')
        self.assertEqual(self.doc.payment_status, 'Payment Rejected')
        self.assertEqual(self.doc.upi_review_note, 'Credit not found')

    def test_duplicate_bank_reference_is_rejected(self):
        self.doc.payment_status = 'Awaiting Verification'
        self.frappe.db.exists.return_value = True
        self.service.post_payment = Mock()
        with self.assertRaisesRegex(ValueError, 'already been used'):
            self.service.review('order', approve=True, reference='123456789012')
        self.service.post_payment.assert_not_called()
        self.assertFalse(self.orders._order_operation.get())

    def test_verify_is_idempotent_and_records_operator(self):
        self.doc.payment_status = 'Awaiting Verification'
        self.frappe.db.exists.return_value = False
        self.service.post_payment = Mock()
        self.service.review('order', approve=True, reference='abc123456')
        self.assertEqual(self.doc.payment_status, 'Paid')
        self.assertEqual(self.doc.upi_verified_by, 'payer')
        self.service.review('order', approve=True, reference='abc123456')
        self.service.post_payment.assert_called_once_with(self.doc, 'ABC123456')

    def test_payment_manager_permission_is_required(self):
        self.scope.require_shop.side_effect = PermissionError
        self.doc.payment_status = 'Awaiting Verification'
        self.service.post_payment = Mock()
        with self.assertRaises(PermissionError):
            self.service.review('order', approve=True, reference='123456789012')
        self.service.post_payment.assert_not_called()

    def test_private_proof_is_not_available_to_delivery_person(self):
        proof = Doc(is_private=1, attached_to_doctype='LC Order',
                    attached_to_name='order', file_name='upi-test.jpg')
        self.scope.identity.return_value = ('rider', ['LC Delivery Person'])
        self.scope.memberships.return_value = [dict(user='rider', shop='shop', enabled=1,
                                                   membership_role='Delivery Person')]
        self.frappe.db.get_value.return_value = self.doc
        self.assertFalse(self.service.file_permission(proof))
        self.scope.identity.return_value = ('payer', ['LC Customer'])
        self.assertTrue(self.service.file_permission(proof))
