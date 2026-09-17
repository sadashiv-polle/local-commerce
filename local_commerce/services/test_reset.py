"""Read-only inventory for a scoped test reset; never exposed as a web API."""

import frappe


def preview():
    """Find commerce records and references that prevent a safe isolated reset."""
    if frappe.session.user != "Administrator":
        frappe.throw("Run the reset inventory as Administrator", frappe.PermissionError)
    from frappe.model.delete_doc import get_dynamic_linked_docs, get_linked_docs

    records = {}
    for row in frappe.get_all(
        "DocType",
        filters={"module": "Local Commerce", "istable": 0, "issingle": 0},
        fields=["name"],
        limit_page_length=0,
    ):
        records[row.name] = frappe.get_all(row.name, pluck="name", limit_page_length=0)
    shops = frappe.get_all("LC Shop", fields=["name", "shop_name", "company"], limit_page_length=0)
    shop_names = [row.name for row in shops]
    orders = records.get("LC Order", [])
    for doctype in ("Payment Entry", "Sales Invoice", "Delivery Note", "Sales Order"):
        records[doctype] = (
            frappe.get_all(
                doctype, filters={"lc_order": ["in", orders]}, pluck="name", limit_page_length=0
            )
            if orders
            else []
        )
    for doctype in ("Stock Entry", "Item"):
        records[doctype] = (
            frappe.get_all(
                doctype, filters={"lc_shop": ["in", shop_names]}, pluck="name", limit_page_length=0
            )
            if shop_names
            else []
        )
    items = records["Item"]
    records["Item Price"] = (
        frappe.get_all(
            "Item Price", filters={"item_code": ["in", items]}, pluck="name", limit_page_length=0
        )
        if items
        else []
    )
    scoped = {doctype: set(names) for doctype, names in records.items()}
    blockers, ledger_counts = [], {}
    managed = {"GL Entry", "Stock Ledger Entry", "Payment Ledger Entry", "Bin"}
    for doctype, names in records.items():
        for name in names:
            doc = frappe.get_doc(doctype, name)
            links = get_linked_docs(doc) + get_dynamic_linked_docs(doc)
            for link in links:
                other = link["reference_doctype"]
                other_name = link["reference_docname"]
                if other_name in scoped.get(other, set()):
                    continue
                if other in managed:
                    continue
                # Featured selections belong to the singleton being reset.
                if other == "LC Store Settings":
                    continue
                # Files/comments are attachments and audit metadata, not business documents.
                if other in {"File", "Comment", "Communication", "ToDo", "Version"}:
                    continue
                blockers.append(
                    {
                        "doctype": doctype,
                        "name": name,
                        "referenced_by": other,
                        "reference": other_name,
                    }
                )
    for doctype in (
        "Payment Entry",
        "Sales Invoice",
        "Delivery Note",
        "Sales Order",
        "Stock Entry",
    ):
        names = records[doctype]
        if names:
            ledger_counts[doctype] = {
                ledger: frappe.db.count(
                    ledger, {"voucher_type": doctype, "voucher_no": ["in", names]}
                )
                for ledger in ("GL Entry", "Stock Ledger Entry", "Payment Ledger Entry")
                if frappe.db.exists("DocType", ledger)
            }
    return {
        "site": frappe.local.site,
        "read_only": True,
        "shops": shops,
        "counts": {doctype: len(names) for doctype, names in records.items()},
        "erp_transactions": {
            doctype: frappe.get_all(
                doctype,
                filters={"name": ["in", records[doctype]]},
                fields=["name", "docstatus", "company"],
                limit_page_length=0,
            )
            if records[doctype]
            else []
            for doctype in (
                "Payment Entry",
                "Sales Invoice",
                "Delivery Note",
                "Sales Order",
                "Stock Entry",
            )
        },
        "ledger_counts": ledger_counts,
        "external_references": blockers,
        "preserve": [
            "Company",
            "Account",
            "Warehouse",
            "Cost Center",
            "User",
            "Customer",
            "Item Group",
            "Role",
            "installed apps",
            "other sites",
        ],
    }
