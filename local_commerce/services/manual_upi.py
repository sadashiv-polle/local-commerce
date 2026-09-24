"""Manually verified UPI receipts. Images are evidence, never payment confirmation."""

import hashlib
import io
import re
from html import escape

import frappe
from frappe.utils import now_datetime, nowdate

from local_commerce.permissions.scope import require_shop
from local_commerce.services.owner import _owner_operation, checked_number, reject


def validate(shop, method=None):
    if not shop.get("upi_enabled"):
        return
    if not re.fullmatch(r"[A-Za-z0-9._-]{2,256}@[A-Za-z0-9.-]{2,64}", shop.get("upi_id") or ""):
        reject("Enter a valid UPI ID, for example fishworld@yourbank")
    account = frappe.db.get_value(
        "Account",
        shop.get("upi_bank_account"),
        ["company", "account_type", "disabled", "is_group", "account_currency"],
        as_dict=True,
    )
    currency = frappe.db.get_value("Company", shop.company, "default_currency")
    if (
        currency != "INR"
        or not account
        or account.company != shop.company
        or account.account_type != "Bank"
        or account.disabled
        or account.is_group
        or account.account_currency != "INR"
    ):
        reject("Choose an active INR bank account belonging to this shop Company for UPI")
    if frappe.db.get_value("Mode of Payment", shop.get("upi_mode_of_payment"), "type") != "Bank":
        reject("Choose a Bank type mode of payment for UPI")
    if shop.get("upi_qr") and not frappe.db.exists(
        "File",
        {
            "file_url": shop.upi_qr,
            "attached_to_doctype": "LC Shop",
            "attached_to_name": shop.name,
            "is_private": 0,
        },
    ):
        reject("Upload the QR image using this shop's UPI settings")


def settings(shop):
    require_shop(shop, "write")
    doc = frappe.get_doc("LC Shop", shop)
    return {
        "enabled": bool(doc.get("upi_enabled")),
        "upi_id": doc.get("upi_id") or "",
        "qr": doc.get("upi_qr") or "",
        "bank_account": doc.get("upi_bank_account") or "",
        "mode_of_payment": doc.get("upi_mode_of_payment") or "",
        "accounts": frappe.get_all(
            "Account",
            filters={
                "company": doc.company,
                "account_type": "Bank",
                "account_currency": "INR",
                "disabled": 0,
                "is_group": 0,
            },
            pluck="name",
        ),
        "modes": frappe.get_all("Mode of Payment", filters={"type": "Bank"}, pluck="name"),
    }


def configure(shop, enabled=0, upi_id="", bank_account="", mode_of_payment=""):
    require_shop(shop, "write")
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", shop)
    doc = frappe.get_doc("LC Shop", shop)
    doc.upi_enabled = enabled in (True, 1, "1", "true")
    doc.upi_id = upi_id.strip()
    doc.upi_bank_account = bank_account or None
    doc.upi_mode_of_payment = mode_of_payment or None
    validate(doc)
    doc.save(ignore_permissions=True)
    return settings(shop)


def save_image(doctype, name, private):
    from frappe.utils.file_manager import save_file
    from PIL import Image, UnidentifiedImageError

    uploaded = frappe.request.files.get("file")
    if not uploaded:
        reject("Choose a payment image")
    data = uploaded.read(5 * 1024 * 1024 + 1)
    if not data or len(data) > 5 * 1024 * 1024:
        reject("Choose a JPG, PNG or WebP image up to 5 MB")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 20000000:
                reject("Choose a JPG, PNG or WebP image under 20 megapixels")
            image.load()
            output = io.BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=90)
            # A unique JPEG comment prevents File content deduplication from attaching
            # identical proofs to another order. It contains no customer metadata.
            marker = frappe.generate_hash(length=32).encode()
            jpeg = output.getvalue()
            data = jpeg[:2] + b"\xff\xfe" + (len(marker) + 2).to_bytes(2, "big") + marker + jpeg[2:]
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        reject("This image could not be read. Choose a JPG, PNG or WebP image")
    return save_file(
        f"upi-{frappe.generate_hash(length=24)}.jpg",
        data,
        doctype,
        name,
        is_private=int(private),
    ).file_url


def upload_qr(shop):
    require_shop(shop, "write")
    doc = frappe.get_doc("LC Shop", shop)
    doc.upi_qr = save_image("LC Shop", shop, False)
    doc.save(ignore_permissions=True)
    return settings(shop)


def locked_order(order):
    doc = frappe.get_doc("LC Order", order)
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    frappe.db.sql("select name from `tabLC Order` where name=%s for update", doc.name)
    doc.reload()
    if doc.payment_method != "Manual UPI":
        reject("This order does not use manual UPI")
    return doc


def payable(doc):
    # UPI proof can be uploaded while the request is waiting for the shop.
    # The shop still cannot accept it until the payment is verified.
    return doc.status in {"Requested", "Accepted", "Preparing", "Ready"}


def upload_proof(order):
    from local_commerce.services import orders

    doc = locked_order(order)
    if frappe.session.user == "Guest" or doc.customer_user != frappe.session.user:
        frappe.throw("Only the order customer can upload payment proof", frappe.PermissionError)
    if not payable(doc) or doc.payment_status not in {"Pending", "Payment Rejected"}:
        reject("Wait for acceptance or the shop's payment review")
    token = orders._order_operation.set(True)
    try:
        doc.upi_proof = save_image("LC Order", doc.name, True)
        doc.payment_status = "Awaiting Verification"
        doc.upi_review_note = ""
        doc.save(ignore_permissions=True)
        from local_commerce.services.notifications import upi_payment_updated

        upi_payment_updated(doc)
        doc.add_comment("Info", "Customer uploaded UPI payment proof; bank verification required.")
    finally:
        orders._order_operation.reset(token)
    return orders.detail(doc.name)


def review(order, approve=0, reference="", note=""):
    from local_commerce.services import orders

    doc = locked_order(order)
    require_shop(doc.shop, "write")
    approved = approve in (True, 1, "1", "true")
    if approved and (doc.payment_status == "Paid" or reconciled_receipt_is_valid(doc)):
        return orders.serialize(doc)
    if doc.payment_status != "Awaiting Verification" or not payable(doc):
        reject("There is no payment awaiting review on this order")
    reference, note = reference.strip().upper(), note.strip()
    if approved and not re.fullmatch(r"[A-Za-z0-9/-]{6,100}", reference):
        reject("Enter the transaction reference from your bank statement (6–100 characters)")
    if not approved and not 3 <= len(note) <= 500:
        reject("Tell the customer why the payment could not be verified (3–500 characters)")
    token = orders._order_operation.set(True)
    owner_token = _owner_operation.set(True)
    try:
        if approved:
            # Account lock serializes reference reuse even across shops sharing a bank account.
            frappe.db.sql(
                "select name from `tabAccount` where name=%s for update", doc.upi_bank_account
            )
            if frappe.db.exists(
                "LC Order",
                {
                    "upi_bank_account": doc.upi_bank_account,
                    "upi_reference": reference,
                    "payment_status": ["in", ["Paid", "Reconciled"]],
                    "name": ["!=", doc.name],
                },
            ):
                reject("This bank transaction has already been used for another order")
            verified_by = frappe.session.user
            post_payment(doc, reference)
            doc.upi_receipt_key = hashlib.sha256(
                f"{doc.upi_bank_account}:{reference}".encode()
            ).hexdigest()
            doc.upi_reference = reference
            doc.upi_verified_by = verified_by
            doc.upi_verified_at = now_datetime()
            doc.payment_status = "Paid"
        else:
            doc.payment_status = "Payment Rejected"
        doc.upi_review_note = note
        doc.save(ignore_permissions=True)
        from local_commerce.services.notifications import upi_payment_updated

        upi_payment_updated(doc)
        doc.add_comment(
            "Info",
            escape(
                "UPI payment verified against bank receipt."
                if approved
                else f"UPI proof rejected: {note}"
            ),
        )
    finally:
        orders._order_operation.reset(token)
        _owner_operation.reset(owner_token)
    return orders.serialize(doc)


def post_payment(doc, reference):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", doc.sales_order)
        account = frappe.get_doc("Account", doc.upi_bank_account)
        if (
            account.company != so.company
            or account.account_type != "Bank"
            or account.disabled
            or account.is_group
            or account.account_currency != "INR"
            or so.currency != "INR"
        ):
            reject("The UPI receiving account is no longer valid for this order")
        invoice = make_sales_invoice(doc.sales_order, ignore_permissions=True)
        invoice.lc_order = doc.name
        invoice.flags.ignore_permissions = True
        invoice.insert(ignore_permissions=True)
        if checked_number(invoice.grand_total, "Invoice total") != checked_number(
            so.grand_total, "Order total"
        ):
            reject("Invoice total changed; contact the administrator before confirming payment")
        invoice.submit()
        payment = get_payment_entry(
            "Sales Invoice",
            invoice.name,
            bank_account=doc.upi_bank_account,
            reference_date=nowdate(),
        )
        payment.reference_no = reference
        payment.reference_date = nowdate()
        payment.mode_of_payment = doc.upi_mode_of_payment
        payment.lc_order = doc.name
        payment.flags.ignore_permissions = True
        payment.insert(ignore_permissions=True)
        payment.submit()
        doc.sales_invoice, doc.payment_entry = invoice.name, payment.name
    finally:
        frappe.set_user(original_user)


def file_permission(doc, user=None, permission_type=None, **kwargs):
    """Payment screenshots are private to the payer and shop payment managers."""
    if not (
        doc.get("is_private")
        and doc.get("attached_to_doctype") == "LC Order"
        and (doc.get("file_name") or "").startswith("upi-")
    ):
        return None
    from local_commerce.permissions.policy import can_access_shop
    from local_commerce.permissions.scope import identity, memberships

    user, roles = identity(user)
    if user == "Guest" or permission_type not in (None, "read"):
        return False
    order = frappe.db.get_value(
        "LC Order", doc.attached_to_name, ["customer_user", "shop"], as_dict=True
    )
    return bool(
        order
        and (
            order.customer_user == user
            or can_access_shop(user, roles, memberships(user), order.shop, "write")
        )
    )


def reconciled_receipt_is_valid(doc):
    """Recognize older UPI status only when submitted accounting proves full receipt."""
    from decimal import Decimal, InvalidOperation

    if (doc.payment_method != "Manual UPI" or doc.payment_status != "Reconciled"
            or not doc.get("upi_verified_by") or not doc.get("upi_verified_at")
            or not doc.get("sales_invoice") or not doc.get("payment_entry")
            or not doc.get("upi_bank_account")):
        return False
    if not (frappe.db.exists("Sales Invoice", doc.sales_invoice)
            and frappe.db.exists("Payment Entry", doc.payment_entry)):
        return False
    invoice = frappe.get_doc("Sales Invoice", doc.sales_invoice)
    payment = frappe.get_doc("Payment Entry", doc.payment_entry)
    so = frappe.get_doc("Sales Order", doc.sales_order)
    if (invoice.docstatus != 1 or payment.docstatus != 1 or invoice.get("is_return")
            or invoice.get("lc_order") != doc.name or payment.get("lc_order") != doc.name
            or invoice.company != so.company or payment.company != so.company
            or invoice.customer != so.customer or payment.party != so.customer
            or payment.party_type != "Customer" or payment.payment_type != "Receive"
            or payment.paid_to != doc.upi_bank_account or invoice.currency != "INR"
            or so.currency != "INR" or payment.paid_to_account_currency != "INR"):
        return False
    try:
        total = Decimal(str(so.grand_total))
        allocated = sum((Decimal(str(row.allocated_amount)) for row in payment.references
                         if row.reference_doctype == "Sales Invoice"
                         and row.reference_name == invoice.name), Decimal(0))
        return (total.is_finite() and total > 0
                and Decimal(str(invoice.grand_total)) == total
                and Decimal(str(invoice.outstanding_amount)) == 0
                and allocated >= total and Decimal(str(payment.received_amount)) >= total)
    except (InvalidOperation, TypeError, ValueError):
        return False
