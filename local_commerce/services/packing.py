"""Owner-confirmed packed weights, using ERPNext's cancellation/amendment workflow."""

import json
from html import escape

import frappe

from local_commerce.services.owner import _owner_operation, balance, checked_number, reject
from local_commerce.services.selling_rules import packed_weights, stock_weight_matches


def finalize(order, modified, weights):
    from local_commerce.services import orders

    doc = frappe.get_doc("LC Order", order)
    orders.authorize(doc, True)
    frappe.db.sql("select name from `tabLC Shop` where name=%s for update", doc.shop)
    frappe.db.sql("select name from `tabLC Order` where name=%s for update", doc.name)
    doc.reload()
    if str(doc.modified) != str(modified):
        reject("This order changed. Refresh before saving packed weights")
    if doc.status not in {"Accepted", "Preparing"}:
        reject("Packed weights can be edited after acceptance and before the order is Ready")
    snapshots = json.loads(doc.get("selling_lines_json") or "[]")
    if not any(line.get("option_id") for line in snapshots):
        reject("This order has no products billed by packed weight")
    try:
        actual = packed_weights(snapshots, frappe.parse_json(weights))
    except (ValueError, TypeError) as exc:
        reject(str(exc))
    so = frappe.get_doc("Sales Order", doc.sales_order)
    if so.docstatus != 1 or len(snapshots) != len(so.items):
        reject("The ERPNext order cannot be repriced here; contact the administrator")
    shop = frappe.get_doc("LC Shop", doc.shop)
    if so.company != shop.company:
        reject("The order Company no longer matches the shop")
    totals = {}
    for index, row in enumerate(so.items):
        quantity = actual.get(index, row.stock_qty)
        totals[row.item_code] = totals.get(row.item_code, 0) + checked_number(
            quantity, "Packed quantity", positive=True
        )
    amended = frappe.copy_doc(so)
    amended.amended_from = so.name
    amended.docstatus = 0
    amended.status = "Draft"
    token = orders._order_operation.set(True)
    owner_token = _owner_operation.set(True)
    frappe.db.savepoint("lc_packing")
    try:
        for index, weight in actual.items():
            snapshot = snapshots[index]
            if snapshot.get("billing") == "Pieces":
                amended.items[index].qty = snapshot["option_quantity"] * snapshot["packs"]
                amended.items[index].conversion_factor = weight / amended.items[index].qty
            else:
                amended.items[index].qty = weight
            rate = (snapshot["piece_price"] if snapshot.get("billing") == "Pieces"
                    else snapshot["rate_per_kg"])
            amended.items[index].rate = rate
            amended.items[index].price_list_rate = rate
            amended.items[index].description = escape(
                f"{amended.items[index].item_name} · {snapshot['label']} × "
                f"{snapshot['packs']:g}; actual packed weight {weight:g} Kg"
            )
            snapshot["actual_weight"] = weight
        amended.ignore_pricing_rule = 1
        subtotal = sum(checked_number(row.qty, "Quantity") * checked_number(row.rate, "Price")
                       for row in amended.items)
        price = orders.pricing_for(shop, subtotal, doc.delivery_distance_km)
        if price["needs_location"]:
            reject("Select a valid delivery location before finalizing packed weights")
        amended.set("taxes", [row for row in amended.taxes
                              if not (row.charge_type == "Actual"
                                      and row.description == "Delivery charge")])
        if price["delivery_fee"]:
            if not shop.delivery_account:
                reject("Set the shop delivery income account before finalizing")
            amended.append("taxes", {"charge_type": "Actual",
                                     "account_head": shop.delivery_account,
                                     "description": "Delivery charge",
                                     "tax_amount": price["delivery_fee"]})
        so.flags.ignore_permissions = True
        so.cancel()
        # Cancelling releases this SO's own reservations before checking the replacement.
        # Keep the shop lock so another checkout cannot take that stock in between.
        for item, quantity in sorted(totals.items()):
            stock = balance(item, shop.warehouse, lock=True, exclude_order=doc.name)
            if quantity > checked_number(stock["available"], "Available stock"):
                reject("Not enough stock for the actual packed weights")
        amended.flags.ignore_permissions = True
        amended.insert(ignore_permissions=True)
        for index, weight in actual.items():
            row = amended.items[index]
            matches = (
                stock_weight_matches(row.stock_qty, weight, row.qty,
                                     row.precision("stock_qty"), row.precision("conversion_factor"))
                if snapshots[index].get("billing") == "Pieces"
                else checked_number(row.stock_qty, "Stock quantity")
                == checked_number(weight, "Packed weight")
            )
            if not matches:
                reject("ERPNext quantity precision changed this weight; enter a supported weight")
            snapshot = snapshots[index]
            if snapshot.get("billing") == "Pieces" and frappe.utils.flt(
                amended.items[index].amount, amended.items[index].precision("amount")
            ) != frappe.utils.flt(
                snapshot["fixed_amount"], amended.items[index].precision("amount")
            ):
                reject("ERPNext changed this piece price; contact the administrator")
        amended.submit()
        from local_commerce.services import fish

        fish.reserve(doc, amended.items)
        doc.sales_order = amended.name
        doc.selling_lines_json = json.dumps(snapshots)
        doc.save(ignore_permissions=True)
        doc.add_comment("Info", escape(
            f"Packed weights confirmed by {frappe.session.user}. "
            f"Sales Order {so.name} amended to {amended.name}; final total {amended.grand_total}."
        ))
        from local_commerce.services.notifications import packed_weight_updated

        packed_weight_updated(doc)
        return orders.serialize(doc)
    except Exception:
        frappe.db.rollback(save_point="lc_packing")
        raise
    finally:
        _owner_operation.reset(owner_token)
        orders._order_operation.reset(token)
