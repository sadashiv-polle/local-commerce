"""Platform-only Easy Split controls; credentials never leave the server."""
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import frappe
from frappe.rate_limiter import rate_limit
from local_commerce.permissions.scope import require_platform
from local_commerce.services.owner import reject
from local_commerce.services.payments import cashfree

VERSION = "2026-01-01"


def context(profile, vendor):
    require_platform()
    if not re.fullmatch(r"[A-Za-z0-9_]{1,100}", vendor or ""):
        reject("Enter a vendor ID using letters, numbers and underscores")
    config = frappe.get_doc("LC Payment Gateway", profile)
    return config, "/easy-split/vendors/" + quote(vendor, safe="")


def vendor_payload(values, create=False):
    values = frappe.parse_json(values)
    allowed = {"name", "email", "phone", "verify_account", "dashboard_access", "schedule_option", "bank", "upi", "kyc_details"}
    if not isinstance(values, dict) or set(values) - allowed:
        reject("Unsupported vendor fields")
    result = {}
    for key in ("name", "email", "phone"):
        value = str(values.get(key) or "").strip()
        if value:
            if len(value) > 140:
                reject("Vendor contact details are too long")
            result[key] = value
        elif create:
            reject("Enter vendor name, email and phone")
    for key in ("verify_account", "dashboard_access"):
        if key in values:
            if not isinstance(values[key], bool):
                reject("Use a checkbox for verification and dashboard access")
            result[key] = values[key]
    if values.get("schedule_option") not in (None, ""):
        try:
            schedule = int(str(values["schedule_option"]))
        except ValueError:
            reject("Enter an integer settlement schedule ID")
        if schedule < 1:
            reject("Enter a valid settlement schedule ID")
        result["schedule_option"] = schedule
    for key, fields in (
        ("bank", {"account_number", "account_holder", "ifsc"}),
        ("upi", {"vpa", "account_holder"}),
        ("kyc_details", {"account_type", "business_type", "pan", "gst", "cin", "uidai", "passport_number", "driving_license", "voter_id"}),
    ):
        obj = values.get(key)
        if obj:
            if not isinstance(obj, dict) or set(obj) - fields:
                reject("Unsupported bank, UPI or KYC fields")
            clean = {k: str(v).strip() for k, v in obj.items() if v not in (None, "")}
            if any(len(v) > 140 for v in clean.values()):
                reject("Vendor detail is too long")
            if clean:
                result[key] = clean
    if result.get("bank") and result.get("upi"):
        reject("Choose bank or UPI, not both")
    if "bank" in result:
        bank = result["bank"]
        if set(bank) != {"account_number", "account_holder", "ifsc"}:
            reject("Enter all bank details")
        bank["ifsc"] = bank["ifsc"].upper()
        if not re.fullmatch(r"\d{6,25}", bank["account_number"]) or not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", bank["ifsc"]):
            reject("Check bank account number and IFSC")
    if "upi" in result and (not result["upi"].get("account_holder") or not re.fullmatch(r"[^\s@]+@[^\s@]+", result["upi"].get("vpa", ""))):
        reject("Enter the UPI ID and account holder")
    if create and (not (result.get("bank") or result.get("upi")) or not result.get("kyc_details")):
        reject("Enter a payout destination and KYC details")
    return result


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=120, seconds=3600)
def inspect(profile, vendor, view="details"):
    config, path = context(profile, vendor)
    paths = {"details": path, "balance": path + "/balances", "documents": "/easy-split/vendor-docs/" + quote(vendor, safe="")}
    if view not in paths:
        reject("Choose vendor details, balance or document status")
    return cashfree.request(config.name, "GET", paths[view], api_version=VERSION)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def save_vendor(profile, vendor, values, mode):
    config, path = context(profile, vendor)
    if mode not in {"create", "update"}:
        reject("Choose create or update")
    payload = vendor_payload(values, mode == "create")
    if mode == "create":
        payload.update(vendor_id=vendor, status="ACTIVE")
    if not payload:
        reject("Enter details to update")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return cashfree.request(config.name, "POST" if mode == "create" else "PATCH",
                            "/easy-split/vendors" if mode == "create" else path,
                            payload, key=f"vendor:{config.name}:{vendor}:{mode}:{digest}", api_version=VERSION)


def transfer_payload(values):
    values = frappe.parse_json(values)
    if not isinstance(values, dict) or set(values) != {"transfer_type", "transfer_from", "transfer_amount", "remark"}:
        reject("Enter transfer type, source, amount and remark")
    if values["transfer_type"] not in {"ON_DEMAND", "ADJUSTMENT"} or values["transfer_from"] not in {"VENDOR", "MERCHANT"}:
        reject("Invalid transfer type or source")
    try:
        amount = Decimal(str(values["transfer_amount"]))
    except InvalidOperation:
        reject("Enter a valid amount")
    if not amount.is_finite() or amount <= 0 or amount > Decimal("999999999") or amount != amount.quantize(Decimal(".01")):
        reject("Enter a positive amount with at most two decimal places")
    remark = str(values["remark"]).strip()
    if not remark or len(remark) > 140:
        reject("Enter a remark of at most 140 characters")
    return {**values, "transfer_amount": float(amount), "remark": remark}


@frappe.whitelist(methods=["POST"])
def prepare_transfer(profile, vendor, values):
    config, _ = context(profile, vendor)
    payload = transfer_payload(values)
    doc = frappe.get_doc({"doctype": "LC Cashfree Transfer", "gateway_profile": config.name,
                         "vendor_id": vendor, "status": "Draft", "payload": json.dumps(payload)})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "environment": config.environment, "payload": payload}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=3600)
def execute_transfer(name):
    require_platform()
    # Commit the intent before the external side effect. A timeout is not a failure.
    frappe.db.sql("select name from `tabLC Cashfree Transfer` where name=%s for update", name)
    doc = frappe.get_doc("LC Cashfree Transfer", name)
    if doc.status != "Draft":
        return {"name": doc.name, "status": doc.status, "response": frappe.parse_json(doc.response or "{}")}
    config, path = context(doc.gateway_profile, doc.vendor_id)
    doc.status = "Unconfirmed"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    try:
        result = cashfree.request(config.name, "POST", path + "/transfer",
                                  frappe.parse_json(doc.payload), key="transfer:" + doc.name, api_version=VERSION)
    except Exception:
        # Do not repeat an uncertain transfer automatically, even after page reload.
        return {"name": doc.name, "status": "Unconfirmed", "message": "Check Cashfree before creating another transfer. This request may have been processed."}
    doc.status = "Accepted"
    doc.response = frappe.as_json(result)
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status, "response": result}


@frappe.whitelist(methods=["POST"])
def activity(profile, vendor):
    context(profile, vendor)
    return frappe.get_all("LC Cashfree Transfer", filters={"gateway_profile": profile, "vendor_id": vendor},
                          fields=["name", "creation", "owner", "status", "payload", "response"],
                          order_by="creation desc", limit_page_length=50)


@frappe.whitelist(methods=["POST"])
def reconciliation(profile, vendor, start_date, end_date, cursor=None):
    from datetime import date
    context(profile, vendor)
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (ValueError, TypeError):
        reject("Choose valid start and end dates")
    if start > end or (end - start).days > 30:
        reject("Choose a date range of at most 31 days")
    if cursor and (not isinstance(cursor, str) or len(cursor) > 2000):
        reject("Invalid pagination cursor")
    return cashfree.request(profile, "POST", "/recon/vendor", {
        "pagination": {"limit": 25, "cursor": cursor or None},
        "filters": {"merchant_vendor_id": vendor, "start_date": start.isoformat() + "T00:00:00Z",
                    "end_date": end.isoformat() + "T23:59:59Z"},
    }, api_version=VERSION)
