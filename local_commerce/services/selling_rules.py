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
            raise ValueError("Count options require a whole-number quantity")
        weight = (number(row.get("estimated_weight"), "Estimated weight", positive=True)
                  if kind == "Count" else quantity)
        ids.add(identifier)
        result.append({"id": identifier, "label": label, "kind": kind,
                       "quantity": float(quantity), "estimated_weight": float(weight)})
    return result


def selected(rows, identifier, packs):
    packs = number(packs, "Quantity", positive=True)
    if packs != packs.to_integral_value():
        raise ValueError("Select a whole number of packs")
    option = next((row for row in options(rows) if row["id"] == identifier), None)
    if not option:
        raise ValueError("Choose an available selling option for this product")
    return {**option, "packs": float(packs),
            "estimated_total_weight": float(Decimal(str(option["estimated_weight"])) * packs)}


def packed_weights(lines, entries):
    expected = {str(index) for index, line in enumerate(lines) if line.get("option_id")}
    if not isinstance(entries, dict) or set(entries) != expected:
        raise ValueError("Enter the total packed weight for every selling-option line")
    return {int(index): float(number(value, "Packed weight", positive=True))
            for index, value in entries.items()}
