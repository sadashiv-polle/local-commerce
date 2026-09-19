"""Configurable count/weight offers sharing one item's kilogram inventory."""

import re
from decimal import Decimal

from local_commerce.services.owner_rules import number


def options(rows):
    if not isinstance(rows, list) or len(rows) > 20:
        raise ValueError("Add up to 20 selling options")
    result, ids = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid selling option")
        identifier = row.get("id", "")
        label = str(row.get("label") or "").strip()
        kind = row.get("kind")
        if (not isinstance(identifier, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", identifier)
                or identifier in ids):
            raise ValueError("Selling options need unique identifiers")
        if not label or len(label) > 100 or kind not in {"Count", "Weight"}:
            raise ValueError("Enter an option name and select Count or Weight")
        quantity = number(row.get("quantity"), "Option quantity", positive=True)
        if kind == "Count" and quantity != quantity.to_integral_value():
            raise ValueError(f'Option "{label}": enter a whole number of pieces (for example, 5). '
                             'Enter kilograms in Approx. weight, or select Sell by Weight.')
        weight = (number(row.get("estimated_weight"), "Estimated weight", positive=True)
                  if kind == "Count" else quantity)
        billing = row.get("billing", "Weight")
        if billing not in {"Weight", "Pieces"} or (kind == "Weight" and billing != "Weight"):
            raise ValueError("Choose weight pricing or piece pricing for count options")
        enabled = row.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("Invalid selling option visibility")
        piece_price = (float(number(row.get("piece_price"), "Price per piece", positive=True))
                       if billing == "Pieces" else None)
        ids.add(identifier)
        result.append({"id": identifier, "label": label, "kind": kind,
                       "quantity": float(quantity), "estimated_weight": float(weight),
                       "billing": billing, "piece_price": piece_price, "enabled": enabled})
    if result and not any(row["enabled"] for row in result):
        raise ValueError("Show at least one selling option")
    return result


def selected(rows, identifier, packs):
    packs = number(packs, "Quantity", positive=True)
    if packs != packs.to_integral_value():
        raise ValueError("Select a whole number of packs")
    option = next((row for row in options(rows)
                   if row["id"] == identifier and row["enabled"]), None)
    if not option:
        raise ValueError("Choose an available selling option for this product")
    return {**option, "packs": float(packs),
            "estimated_total_weight": float(Decimal(str(option["estimated_weight"])) * packs)}


def packed_weights(lines, entries):
    expected = {str(index) for index, line in enumerate(lines)
                if line.get("option_id") and not line.get("preweighed")}
    if not isinstance(entries, dict) or set(entries) != expected:
        raise ValueError("Enter the total packed weight for every selling-option line")
    return {int(index): float(number(value, "Packed weight", positive=True))
            for index, value in entries.items()}


def stock_weight_matches(actual, expected, pieces, stock_precision, conversion_precision):
    """Allow configured UOM rounding; never rewrite ledger quantities.

    A pack's kg/piece factor can recur (0.5 / 3). ERPNext rounds that factor
    and the resulting stock quantity separately. Reservations and deliveries
    must continue using ERPNext's resulting stock_qty, not the display estimate.
    Reject discrepancies above one percent even with very coarse settings.
    """
    actual, expected, pieces = (Decimal(str(value)) for value in (actual, expected, pieces))
    if not all(value.is_finite() and value > 0 for value in (actual, expected, pieces)):
        return False
    tolerance = (Decimal(10) ** -stock_precision / 2
                 + pieces * Decimal(10) ** -conversion_precision / 2)
    return abs(actual - expected) <= min(tolerance, expected * Decimal("0.01"))
