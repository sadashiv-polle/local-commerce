"""Delivery prices use item subtotal and straight-line shop distance."""

from decimal import ROUND_HALF_UP, Decimal


def delivery_price(
    subtotal, base=0, per_km=0, included_km=0, distance=None, minimum=0, free_above=0
):
    subtotal, base, per_km, included_km, minimum, free_above = (
        Decimal(str(value or 0))
        for value in (subtotal, base, per_km, included_km, minimum, free_above)
    )
    if min(subtotal, base, per_km, included_km, minimum, free_above) < 0:
        raise ValueError("Delivery pricing values cannot be negative")
    free = bool(free_above and subtotal >= free_above)
    needs_location = bool(per_km and distance is None and not free)
    extra_distance = max(Decimal(0), Decimal(str(distance or 0)) - included_km)
    fee = Decimal(0) if free else base + per_km * extra_distance
    return {
        "delivery_fee": float(fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "minimum_remaining": float(max(Decimal(0), minimum - subtotal)),
        "free_delivery_remaining": float(max(Decimal(0), free_above - subtotal))
        if free_above
        else None,
        "free_delivery": free,
        "needs_location": needs_location,
    }
