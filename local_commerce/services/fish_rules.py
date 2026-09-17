"""Expiry and earliest-expiry-first allocation independent of ERPNext."""

from datetime import timedelta
from decimal import Decimal

from local_commerce.services.owner_rules import number


def expiry(received_at, hours):
    duration = number(hours, "Stock validity hours", positive=True)
    if duration > 8760:
        raise ValueError("Stock validity cannot exceed 8760 hours")
    return received_at + timedelta(seconds=float(duration * 3600))


def allocate(lots, quantity, reserved, now):
    needed = number(quantity, "Fish quantity", positive=True)
    result = []
    for lot in sorted(lots, key=lambda row: (row["expires_at"], row["name"])):
        if lot["expires_at"] <= now:
            continue
        available = max(Decimal(0), Decimal(str(lot["remaining"]))
                        - Decimal(str(reserved.get(lot["name"], 0))))
        take = min(needed, available)
        if take:
            result.append({"lot": lot["name"], "item": lot["item"], "quantity": float(take)})
            needed -= take
        if not needed:
            return result
    raise ValueError("Not enough unexpired fish stock; record fresh stock or reduce the order")
