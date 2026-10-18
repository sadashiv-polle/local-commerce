"""Display breakdown of the saved Sales Order; never calculate a new payable amount."""


def checkout_bill(so):
    subtotal = float(so.total or 0)
    discount = float(so.discount_amount or 0)
    delivery = sum(float(t.tax_amount or 0) for t in so.taxes if t.description == 'Delivery charge')
    # Inclusive taxes already form part of item amounts. Show only the remaining
    # adjustment, keeping the breakdown equal to the gateway's grand_total.
    return dict(subtotal=subtotal, discount=discount, delivery=delivery,
                taxes=float(so.grand_total or 0) - subtotal + discount - delivery)


def prepare_sales_order(shop, items, customer, delivery_date, delivery_fee, **extra):
    """Shared unsaved ERP document for checkout quotes and real order creation."""
    import frappe
    from frappe.utils import nowdate
    from erpnext.controllers.accounts_controller import get_taxes_and_charges

    so = frappe.get_doc(dict(
        doctype='Sales Order', company=shop.company, customer=customer,
        transaction_date=nowdate(), delivery_date=delivery_date, order_type='Sales',
        selling_price_list=shop.selling_price_list,
        currency=frappe.db.get_value('Company', shop.company, 'default_currency'),
        conversion_rate=1, plc_conversion_rate=1, ignore_pricing_rule=1,
        set_warehouse=shop.warehouse, taxes_and_charges=shop.order_tax_template,
        items=items, **extra,
    ))
    if shop.order_tax_template:
        so.set('taxes', get_taxes_and_charges('Sales Taxes and Charges Template', shop.order_tax_template))
    so.flags.ignore_permissions = True
    so.set_missing_values()
    if delivery_fee:
        so.append('taxes', dict(charge_type='Actual', account_head=shop.delivery_account,
                               description='Delivery charge', tax_amount=delivery_fee))
    if getattr(shop, 'gst_enabled', 0):
        from local_commerce.services.gst.config import apply_tax
        apply_tax(shop, so, delivery_fee)
    if getattr(shop, 'business_model', None) == 'Owned shop':
        so.cost_center = shop.cost_center
        for row in [*so.items, *so.taxes]:
            row.cost_center = shop.cost_center
    return so
