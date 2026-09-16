"""Build a reviewable reorder using current product prices and stock."""


def reorder_line(previous, product):
    name = previous["name"]
    if product is None:
        return None, f"{name}: no longer available from this shop."
    if previous["uom"] != product["uom"]:
        return None, f"{name}: the selling unit changed; please add it from the shop."
    if product["rate"] is None or product["available"] <= 0:
        return None, f"{name}: currently sold out or unavailable for ordering."
    quantity = min(float(previous["quantity"]), float(product["available"]))
    messages = []
    if quantity < float(previous["quantity"]):
        messages.append(f"quantity reduced to {quantity:g} {product['uom']} for current stock")
    if float(previous["rate"]) != float(product["rate"]):
        messages.append("price updated to the current shop price")
    return {
        **product,
        "quantity": quantity,
    }, f"{name}: {'; '.join(messages)}." if messages else None
