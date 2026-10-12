"""Display breakdown of the saved Sales Order; never calculate a new payable amount."""


def checkout_bill(so):
    subtotal = float(so.total or 0)
    discount = float(so.discount_amount or 0)
    delivery = sum(float(t.tax_amount or 0) for t in so.taxes if t.description == 'Delivery charge')
    # Inclusive taxes already form part of item amounts. Show only the remaining
    # adjustment, keeping the breakdown equal to the gateway's grand_total.
    return dict(subtotal=subtotal, discount=discount, delivery=delivery,
                taxes=float(so.grand_total or 0) - subtotal + discount - delivery)
