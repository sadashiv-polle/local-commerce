"""Cashfree PG with static Easy Split. No browser result is trusted as payment."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import quote
from zoneinfo import ZoneInfo

import frappe
import requests

from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject
from local_commerce.services.payments.rules import money, split_amounts, successful_payment

SHOP_FIELDS = (
    "cashfree_enabled",
    "cashfree_gateway",
    "cashfree_settlement_mode",
    "cashfree_vendor_id",
    "cashfree_commission_type",
    "cashfree_commission",
    "cashfree_clearing_account",
    "cashfree_commission_account",
    "cashfree_mode_of_payment",
)


class CreationUncertain(Exception):
    """A create call may have succeeded remotely; reconcile before retrying."""


def safe_provider_message(value, secrets, payload=None):
    if not isinstance(value, str):
        return "No provider explanation supplied"
    private = list(secrets)

    def collect(node):
        if isinstance(node, dict):
            for child in node.values():
                collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)
        elif isinstance(node, str) and len(node) >= 3:
            private.append(node)

    collect(payload)
    for secret in sorted(filter(None, private), key=len, reverse=True):
        value = value.replace(secret, "[redacted]")
        value = value.replace(json.dumps(secret)[1:-1], "[redacted]")
    value = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+", "[redacted]", value)
    value = re.sub(r"\b\d[\d ()+-]{6,}\d\b|\b[A-Za-z0-9_-]{24,}\b", "[redacted]", value)
    return escape(" ".join(value.split())[:500])


def request_failure(response, method, path, reference, secrets, payload=None, recover=False):
    """Expose bounded error codes/field hints, never echoed customer values or secrets."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    code = body.get("code")
    if (
        not isinstance(code, str)
        or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", code)
        or any(secret and secret in code for secret in secrets)
    ):
        code = "unknown_error"
    message = body.get("message")
    message = message.lower() if isinstance(message, str) else ""
    hint = "Use the reference below when contacting the shop administrator."
    for field, explanation in (
        ("customer_phone", "Check the customer's ten-digit phone number."),
        ("customer_id", "Cashfree rejected the customer reference."),
        ("order_expiry_time", "Cashfree rejected the payment expiry time."),
        ("return_url", "Check the site's payment return URL configuration."),
        ("notify_url", "Check the site's webhook URL configuration."),
        ("order_splits", "Check the shop's Easy Split configuration and approved vendor."),
        ("vendor", "Check the shop's Easy Split configuration and approved vendor."),
        ("order_amount", "Cashfree rejected the order amount."),
        ("order_currency", "Check the order currency and gateway currency support."),
        ("order_id", "Cashfree rejected the payment order reference."),
    ):
        if field in code or field in message:
            hint = explanation
            break
    operation = (
        "create payment"
        if method == "POST" and path == "/orders"
        else "fetch payment order"
        if re.fullmatch(r"/orders/[^/]+", path)
        else "fetch payments"
        if path.endswith("/payments")
        else "fetch refunds"
        if path.endswith("/refunds")
        else "gateway request"
    )
    detail = (
        f"Cashfree could not {operation} (HTTP {response.status_code}; {code}). "
        f"{hint} Provider: {safe_provider_message(body.get('message'), secrets, payload)}. "
        f"Reference: {reference}"
    )
    # A file logger survives request rollback. Do not pass response/payload/headers.
    frappe.logger("local_commerce_cashfree", allow_site=True).error(detail)
    if recover and response.status_code in {409, 500, 502, 503, 504}:
        raise CreationUncertain(detail)
    reject(detail)


def request(profile, method, path, payload=None, key=None, missing=False, recover=False):
    recover = recover and method == "POST" and path == "/orders" and bool(key)
    config = frappe.get_doc("LC Payment Gateway", profile)
    base = {
        "sandbox": "https://sandbox.cashfree.com/pg",
        "production": "https://api.cashfree.com/pg",
    }[config.environment]
    reference = str(uuid.uuid4())
    headers = {
        "x-client-id": config.client_id,
        "x-client-secret": config.get_password("client_secret"),
        "x-api-version": "2025-01-01",
        "Content-Type": "application/json",
        "x-request-id": reference,
    }
    if key:
        headers["x-idempotency-key"] = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
    try:
        response = requests.request(
            method,
            base + path,
            json=payload,
            headers=headers,
            timeout=(5, 25),
            allow_redirects=False,
        )
    except requests.RequestException:
        if recover:
            raise CreationUncertain(
                "Cashfree did not confirm payment creation. Retry using this same order. "
                f"Reference: {reference}"
            ) from None
        reject("Cashfree could not be reached. Retry; the same payment reference will be reused")
    if missing and response.status_code == 404:
        return None
    if not 200 <= response.status_code < 300:
        request_failure(
            response,
            method,
            path,
            reference,
            (headers["x-client-id"], headers["x-client-secret"]),
            payload,
            recover,
        )
    return response.json()


def create_payment(profile, payload, key):
    """At most two identical POSTs; never change identity, totals or settlement."""
    path = "/orders/" + quote(payload["order_id"], safe="")
    for attempt in range(2):
        try:
            return request(profile, "POST", "/orders", payload, key, recover=True)
        except CreationUncertain as exc:
            # A 500/timeout/duplicate response does not prove creation failed.
            remote = request(profile, "GET", path, missing=True)
            if remote is not None:
                successful_payment(
                    remote,
                    [],
                    payload["order_id"],
                    payload["order_amount"],
                    payload["order_currency"],
                )
                return remote
            if attempt:
                reject(str(exc))


def available(shop):
    return bool(
        shop.get("cashfree_enabled")
        and shop.get("cashfree_gateway")
        and frappe.db.get_value("LC Payment Gateway", shop.cashfree_gateway, "enabled")
    )


def settlement_mode(shop):
    # Existing shops/orders retain Easy Split unless explicitly changed by an admin.
    mode = shop.get("cashfree_settlement_mode") or "Easy Split"
    if mode not in {"Easy Split", "Direct merchant"}:
        reject("Choose Main merchant account or Easy Split")
    return mode


def validate_shop(shop, method=None):
    previous = shop.get_doc_before_save()
    if not previous and shop.is_new() and shop.get("cashfree_enabled"):
        require_platform()
    if previous and any(previous.get(f) != shop.get(f) for f in SHOP_FIELDS):
        require_platform()
    if not shop.get("cashfree_enabled"):
        return
    if not shop.get("cashfree_gateway") or not frappe.db.exists(
        "LC Payment Gateway", shop.cashfree_gateway
    ):
        reject("Select a Cashfree gateway profile")
    split = settlement_mode(shop) == "Easy Split"
    if split:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", shop.get("cashfree_vendor_id") or ""):
            reject("Enter this shop's approved Cashfree Easy Split vendor ID")
        value = money(shop.get("cashfree_commission") or 0)
        if shop.get("cashfree_commission_type") not in {"Fixed", "Percentage"}:
            reject("Select a commission type")
        if shop.cashfree_commission_type == "Percentage" and value >= 100:
            reject("Percentage commission must be below 100")
    accounts = [("cashfree_clearing_account", "Asset")]
    if split:
        accounts.append(("cashfree_commission_account", "Expense"))
    for field, root in accounts:
        account = frappe.db.get_value(
            "Account",
            shop.get(field),
            ["company", "root_type", "is_group", "disabled", "account_currency", "account_type"],
            as_dict=True,
        )
        if (
            not account
            or account.company != shop.company
            or account.root_type != root
            or account.is_group
            or account.disabled
            or account.account_currency != "INR"
            or (root == "Asset" and account.account_type != "Bank")
        ):
            reject(f"Select an active INR {root} account for {field.replace('_', ' ')}")
    if frappe.db.get_value("Company", shop.company, "default_currency") != "INR":
        reject("Cashfree checkout currently supports INR shops")
    if frappe.db.get_value("Mode of Payment", shop.cashfree_mode_of_payment, "type") != "Bank":
        reject("Select a Bank type Mode of Payment")


def snapshot(order, shop, so):
    validate_shop(shop)
    mode = settlement_mode(shop)
    split = mode == "Easy Split"
    vendor, commission = (
        split_amounts(so.grand_total, shop.cashfree_commission_type, shop.cashfree_commission or 0)
        if split
        else (money(0), money(0))
    )
    if money(so.grand_total) < 1 or money(so.grand_total) != money(
        so.rounded_total or so.grand_total
    ):
        reject("Cashfree requires an unrounded order total of at least INR 1")
    order.gateway_profile = shop.cashfree_gateway
    order.gateway_order_id = "lc_" + hashlib.sha256(order.name.encode()).hexdigest()[:40]
    order.gateway_snapshot = frappe.as_json(
        {
            "amount": str(money(so.grand_total)),
            "currency": so.currency,
            "settlement_mode": mode,
            "vendor_id": shop.cashfree_vendor_id if split else None,
            "vendor_amount": str(vendor),
            "commission": str(commission),
            "clearing_account": shop.cashfree_clearing_account,
            "commission_account": shop.cashfree_commission_account if split else None,
            "mode_of_payment": shop.cashfree_mode_of_payment,
            "expires_at": (
                frappe.utils.now_datetime()
                .replace(tzinfo=ZoneInfo(frappe.utils.get_system_timezone()))
                .astimezone(timezone.utc)
                + timedelta(minutes=30)
            ).isoformat(),
        }
    )


def begin_operation(order):
    """Start a standalone payment operation, without holding inventory row locks.

    Call only from a read-only request/job preflight. End that read transaction
    so MariaDB REPEATABLE READ cannot reuse a snapshot from before the mutex.
    Never commit a caller's pending writes. Keep the per-order advisory lock
    until the *final* commit/rollback (including accounting), not just HTTP I/O.
    """
    if frappe.db.transaction_writes:
        reject("Finish the current transaction before verifying Cashfree payment")
    frappe.db.commit()
    key = "lc_cf_" + hashlib.sha256(f"{frappe.local.site}:{order}".encode()).hexdigest()[:50]
    result = frappe.db.sql("select get_lock(%s, 0)", (key,))
    if not result or result[0][0] != 1:
        reject("Payment is being updated. Please retry in a moment")

    def release():
        frappe.db.sql("select release_lock(%s)", (key,))

    frappe.db.after_commit.add(release)
    frappe.db.after_rollback.add(release)


def payment_order(order):
    doc = frappe.get_doc("LC Order", order)
    if doc.payment_method != "Cashfree":
        reject("This order does not use Cashfree")
    return doc


def locked(order):
    doc = frappe.get_doc("LC Order", order)
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    doc = frappe.get_doc("LC Order", order, for_update=True)
    if doc.payment_method != "Cashfree":
        reject("This order does not use Cashfree")
    return doc


def save(doc):
    from local_commerce.services.orders import _order_operation

    token = _order_operation.set(True)
    try:
        doc.save(ignore_permissions=True)
    finally:
        _order_operation.reset(token)


def checkout(order):
    doc = payment_order(order)
    if frappe.session.user == "Guest" or doc.customer_user != frappe.session.user:
        frappe.throw("Only the order customer can pay", frappe.PermissionError)
    begin_operation(order)
    doc = payment_order(order)
    if doc.customer_user != frappe.session.user:
        frappe.throw("Only the order customer can pay", frappe.PermissionError)
    if doc.status == "Cancelled" or doc.payment_status in {"Paid", "Refunded"}:
        reject("This order is not payable")
    shop = frappe.get_doc("LC Shop", doc.shop)
    if not available(shop) or not frappe.db.get_value(
        "LC Payment Gateway", doc.gateway_profile, "enabled"
    ):
        reject("Cashfree checkout is currently disabled")
    snap = json.loads(doc.gateway_snapshot)
    path = "/orders/" + quote(doc.gateway_order_id, safe="")
    remote = request(doc.gateway_profile, "GET", path, missing=True)
    if remote is None:
        if datetime.fromisoformat(snap["expires_at"]) <= datetime.now(timezone.utc):
            reject("This payment window expired. Cancel this request and place a new order")
        phone = re.sub(r"\D", "", doc.phone or "")
        if len(phone) == 12 and phone.startswith("91"):
            phone = phone[2:]
        if len(phone) != 10:
            reject("Cashfree requires a ten-digit Indian customer phone number")
        origin = frappe.utils.get_url().rstrip("/")
        if frappe.db.get_value(
            "LC Payment Gateway", doc.gateway_profile, "environment"
        ) == "production" and not origin.startswith("https://"):
            reject("Production checkout requires an HTTPS site URL")
        payload = {
            "order_id": doc.gateway_order_id,
            "order_amount": float(snap["amount"]),
            "order_currency": snap["currency"],
            "order_expiry_time": snap["expires_at"],
            "customer_details": {
                "customer_id": hashlib.sha256(doc.customer_user.encode()).hexdigest()[:40],
                "customer_phone": phone,
            },
            "order_meta": {
                "return_url": origin + "/local-commerce#/orders?order=" + doc.name,
                "notify_url": origin + "/api/method/local_commerce.api.cashfree.webhook",
            },
        }
        if snap.get("settlement_mode", "Easy Split") == "Easy Split":
            payload["order_splits"] = [
                {"vendor_id": snap["vendor_id"], "amount": float(snap["vendor_amount"])}
            ]
        remote = create_payment(doc.gateway_profile, payload, doc.gateway_order_id)
    successful_payment(remote, [], doc.gateway_order_id, snap["amount"], snap["currency"])
    if remote.get("order_status") != "ACTIVE":
        reject("This payment session is no longer active. Refresh payment status")
    return {
        "payment_session_id": remote["payment_session_id"],
        "environment": frappe.db.get_value(
            "LC Payment Gateway", doc.gateway_profile, "environment"
        ),
    }


def sync(order, authorize=True):
    from local_commerce.services import orders

    doc = payment_order(order)
    if authorize:
        orders.authorize(doc)
    begin_operation(order)
    doc = payment_order(order)
    if authorize:
        orders.authorize(doc)
    snap = json.loads(doc.gateway_snapshot)
    path = "/orders/" + quote(doc.gateway_order_id, safe="")
    remote = request(doc.gateway_profile, "GET", path, missing=True)
    payments = request(doc.gateway_profile, "GET", path + "/payments") if remote else []
    payment_id = (
        successful_payment(remote, payments, doc.gateway_order_id, snap["amount"], snap["currency"])
        if remote
        else None
    )
    refunds = request(doc.gateway_profile, "GET", path + "/refunds") if payment_id else []
    # Only local stock/accounting work below this point holds the shop lock.
    doc = locked(order)
    if remote is None:
        if doc.payment_status not in {"Paid", "Refunded"}:
            doc.payment_status = (
                "Failed"
                if datetime.fromisoformat(snap["expires_at"]) <= datetime.now(timezone.utc)
                else "Pending"
            )
            save(doc)
        return {"payment_status": doc.payment_status, "accounting_pending": False}
    if payment_id:
        if doc.gateway_payment_id and doc.gateway_payment_id != payment_id:
            reject("Payment reference changed; administrator review required")
        doc.gateway_payment_id = payment_id
        refunded = sum(
            {
                str(row["cf_refund_id"]): money(row["refund_amount"])
                for row in refunds
                if row.get("refund_status") == "SUCCESS"
                and row.get("order_id") == doc.gateway_order_id
                and row.get("refund_currency") == snap["currency"]
            }.values(),
            money(0),
        )
        refunded = max(refunded, money(doc.gateway_refunded_amount or 0))
        doc.gateway_refunded_amount = float(refunded)
        if refunded:
            doc.payment_status = "Refunded" if refunded >= money(snap["amount"]) else "Paid"
            doc.gateway_accounting_error = (
                "Refund recorded by Cashfree. Administrator must reconcile the credit note "
                "and refund accounting before further fulfilment."
            )
            save(doc)
            return {"payment_status": doc.payment_status, "accounting_pending": True}
        if doc.payment_status != "Refunded":
            doc.payment_status = "Paid"
        save(doc)
        # Persist receipt even if stock or bookkeeping needs manual attention.
        if not doc.payment_entry and doc.payment_status == "Paid":
            frappe.db.savepoint("cashfree_accounting")
            try:
                previous = doc.status
                book_payment(doc)
                doc.gateway_accounting_error = ""
                save(doc)
                if previous != doc.status:
                    orders.order_notifications.status_changed(doc, previous)
            except Exception:
                frappe.db.rollback(save_point="cashfree_accounting")
                doc.reload()
                doc.gateway_accounting_error = (
                    "Payment received. Accounting/stock needs administrator review; "
                    "use Retry verification."
                )
                frappe.log_error(title="Cashfree accounting requires review", message=doc.name)
            save(doc)
    elif doc.payment_status not in {"Paid", "Refunded"}:
        doc.payment_status = (
            "Failed"
            if remote.get("order_status") in {"EXPIRED", "TERMINATED"}
            or (
                payments
                and all(p.get("payment_status") in {"FAILED", "USER_DROPPED"} for p in payments)
            )
            else "Pending"
        )
        save(doc)
    return {
        "payment_status": doc.payment_status,
        "accounting_pending": bool(doc.gateway_accounting_error),
    }


def book_payment(doc):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

    from local_commerce.services import fish, orders
    from local_commerce.services.owner import _owner_operation

    snap = json.loads(doc.gateway_snapshot)
    token, owner_token = orders._order_operation.set(True), _owner_operation.set(True)
    user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", doc.sales_order)
        accounts = [("clearing_account", "Asset")]
        if money(snap["commission"]):
            accounts.append(("commission_account", "Expense"))
        for field, root in accounts:
            account = frappe.get_doc("Account", snap[field])
            if (
                account.company != so.company
                or account.root_type != root
                or account.disabled
                or account.is_group
                or account.account_currency != "INR"
                or (root == "Asset" and account.account_type != "Bank")
            ):
                reject("The Cashfree accounting account is no longer valid for this order")
        if doc.status == "Cancelled":
            reject("Paid cancelled order needs a refund review")
        if so.docstatus == 0:
            fish.validate_order(doc)
            orders._accept_sales_order(doc, so)
            doc.status = "Accepted"
        if so.docstatus != 1:
            reject("Sales Order is not submitted")
        invoice = make_sales_invoice(so.name, ignore_permissions=True)
        invoice.lc_order = doc.name
        invoice.insert(ignore_permissions=True)
        if money(invoice.grand_total) != money(snap["amount"]):
            reject("Invoice amount changed")
        invoice.submit()
        payment = get_payment_entry(
            "Sales Invoice",
            invoice.name,
            bank_account=snap["clearing_account"],
            reference_date=frappe.utils.nowdate(),
        )
        payment.reference_no = doc.gateway_payment_id
        payment.reference_date = frappe.utils.nowdate()
        payment.mode_of_payment = snap["mode_of_payment"]
        payment.lc_order = doc.name
        payment.insert(ignore_permissions=True)
        payment.submit()
        commission = float(snap["commission"])
        if commission:
            frappe.get_doc(
                {
                    "doctype": "Journal Entry",
                    "voucher_type": "Journal Entry",
                    "company": so.company,
                    "posting_date": frappe.utils.nowdate(),
                    "user_remark": "Cashfree marketplace commission for " + doc.name,
                    "accounts": [
                        {
                            "account": snap["commission_account"],
                            "debit_in_account_currency": commission,
                            "cost_center": frappe.db.get_value("LC Shop", doc.shop, "cost_center"),
                        },
                        {
                            "account": snap["clearing_account"],
                            "credit_in_account_currency": commission,
                        },
                    ],
                }
            ).insert(ignore_permissions=True).submit()
        doc.sales_invoice, doc.payment_entry = invoice.name, payment.name
    finally:
        frappe.set_user(user)
        orders._order_operation.reset(token)
        _owner_operation.reset(owner_token)


def prepare_cancellation(doc):
    """Called after authorization, before orders.change takes inventory locks."""
    begin_operation(doc.name)
    doc = payment_order(doc.name)
    from local_commerce.services import orders

    orders.authorize(doc)
    ensure_unpaid(doc)
    remote = request(doc.gateway_profile, "GET", "/orders/" + doc.gateway_order_id, missing=True)
    snap = json.loads(doc.gateway_snapshot)
    if remote:
        successful_payment(remote, [], doc.gateway_order_id, snap["amount"], snap["currency"])
    if remote and remote.get("order_status") not in {"EXPIRED", "TERMINATED"}:
        reject("The payment window is still open. Refresh payment status or wait for it to expire")
    return (doc.name, doc.gateway_profile, doc.gateway_order_id, doc.gateway_snapshot)


def ensure_unpaid(doc):
    if doc.payment_status in {"Paid", "Refunded"} or doc.payment_entry:
        reject("Paid orders need a refund and accounting review before cancellation")


def ensure_cancellable(doc, evidence):
    ensure_unpaid(doc)
    if evidence != (doc.name, doc.gateway_profile, doc.gateway_order_id, doc.gateway_snapshot):
        reject("Payment details changed. Refresh and try again")


def reconcile_pending():
    """Recover missed payment callbacks; each order has its own transaction."""
    names = frappe.get_all(
        "LC Order",
        filters={"payment_method": "Cashfree", "status": "Requested"},
        pluck="name",
        order_by="modified asc",
        limit_page_length=20,
    )
    for name in names:
        try:
            sync(name, authorize=False)
            # Finish accounting and release its locks before another provider request.
            frappe.db.commit()
            doc = frappe.get_doc("LC Order", name)
            if doc.payment_status == "Failed":
                from local_commerce.services.orders import change

                change(name, "Cancelled", "Cashfree payment window expired")
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
