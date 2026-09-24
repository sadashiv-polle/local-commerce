import traceback

import frappe
from frappe.rate_limiter import rate_limit

from local_commerce.services import manual_upi


@frappe.whitelist(methods=["GET"])
def settings(shop):
    return manual_upi.settings(shop)


@frappe.whitelist(methods=["POST"])
def configure(shop, enabled=0, upi_id="", bank_account="", mode_of_payment=""):
    return manual_upi.configure(shop, enabled, upi_id, bank_account, mode_of_payment)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=3600)
def upload_qr(shop):
    return manual_upi.upload_qr(shop)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=3600)
def upload_proof(order):
    return manual_upi.upload_proof(order)


@frappe.whitelist(methods=["POST"])
def review(order, approve=0, reference="", note=""):
    try:
        return manual_upi.review(order, approve, reference, note)
    except Exception:
        # Keep the original traceback in a dedicated site log even when Frappe
        # does not create an Error Log for framework validation failures.
        if frappe.local.response.get("lc_message"):
            raise
        reference_id = frappe.generate_hash(length=10)
        frappe.logger("local_commerce_upi", allow_site=True).error(
            "UPI review %s for order %s\n%s", reference_id, order, traceback.format_exc()
        )
        frappe.db.rollback()
        from local_commerce.services.owner import reject

        reject(
            "Payment review could not be completed. No changes were saved. "
            f"Ask the administrator to check UPI error {reference_id}."
        )
