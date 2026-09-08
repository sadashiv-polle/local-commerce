"""Pure validation shared by owner pricing and physical-stock operations."""

from decimal import Decimal, InvalidOperation


def number(value, label, positive=False, precision=6):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} must be a valid number") from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError(
            f"{label} must be {'greater than zero' if positive else 'zero or greater'}"
        )
    if result > Decimal("1000000000") or result != result.quantize(Decimal(10) ** -precision):
        raise ValueError(f"{label} is too large or has more than {precision} decimal places")
    return result


def stock_change(action, quantity, unit_cost, actual, reserved, whole_units=False):
    if action not in {"Add", "Remove"}:
        raise ValueError("Choose Add or Remove")
    qty = number(quantity, "Quantity", positive=True)
    if whole_units and qty != qty.to_integral_value():
        raise ValueError("This unit requires a whole-number quantity")
    cost = (
        number(unit_cost, "Unit cost", positive=action == "Add") if action == "Add" else Decimal(0)
    )
    if action == "Remove" and qty > max(Decimal(0), Decimal(str(actual)) - Decimal(str(reserved))):
        raise ValueError("Not enough unreserved stock in this warehouse")
    return qty, cost


def availability(actual, paused=False, archived=False):
    if archived:
        return "Archived"
    if paused:
        return "Manually sold out"
    return "In stock" if actual > 0 else "Out of stock"
