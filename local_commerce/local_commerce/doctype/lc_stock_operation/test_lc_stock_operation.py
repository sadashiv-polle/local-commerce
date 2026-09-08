import frappe
from frappe.tests.utils import FrappeTestCase


class TestLCStockOperation(FrappeTestCase):
    def test_document_validation_does_not_allow_forged_audit_records(self):
        doc = frappe.get_doc({"doctype": "LC Stock Operation"})
        with self.assertRaises(frappe.PermissionError):
            doc.validate()

    def test_audit_records_cannot_be_deleted_even_by_administrator(self):
        doc = frappe.get_doc({"doctype": "LC Stock Operation"})
        with self.assertRaises(frappe.PermissionError):
            doc.on_trash()
