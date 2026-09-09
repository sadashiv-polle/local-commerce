"""Validation shared by the delivery request service and standalone tests."""

from decimal import Decimal

from local_commerce.services.owner_rules import number

TRANSITIONS = {
    "Requested": {"Accepted", "Cancelled"},
    "Accepted": {"Preparing", "Cancelled"},
    "Preparing": {"Ready", "Cancelled"},
    "Ready": {"Cancelled"},
    "Cancelled": set(),
}


def transition(current, target, customer=False):
    if current == target:
        return False
    if target not in TRANSITIONS.get(current, set()) or (
        customer and (current != "Requested" or target != "Cancelled")
    ):
        raise ValueError("This order status change is not allowed")
    return True


def cart_rows(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 30:
        raise ValueError("Choose between 1 and 30 products")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("item"), str):
            raise ValueError("Invalid product")
        item = row["item"]
        if not item or len(item) > 140 or item in result:
            raise ValueError("Invalid or duplicate product")
        result[item] = number(row.get("quantity"), "Quantity", positive=True)
    return [{"item": item, "quantity": str(result[item])} for item in sorted(result)]


def address_fields(address):
    if not isinstance(address, dict):
        raise ValueError("Enter a delivery address")
    limits = {"recipient": 140, "phone": 30, "line1": 140, "city": 100, "postal_code": 20}
    result = {}
    for key, limit in limits.items():
        value = str(address.get(key) or "").strip()
        if not value or len(value) > limit:
            raise ValueError(f"Enter a valid {key.replace('_', ' ')}")
        result[key] = value
    if sum(c.isdigit() for c in result["phone"]) < 7:
        raise ValueError("Enter a valid phone number")
    result["postal_code"] = result["postal_code"].upper()
    return result


def whole_quantity(quantity, whole):
    value = Decimal(str(quantity))
    if whole and value != value.to_integral_value():
        raise ValueError("This product requires a whole-number quantity")
