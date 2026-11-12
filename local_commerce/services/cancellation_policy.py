"""Marketplace policy v1. All calculations are integer paise; no provider I/O."""
from decimal import Decimal, InvalidOperation

VERSION = 1
BEFORE_PREPARING = {'Requested', 'Accepted'}
AFTER_PREPARING = {'Preparing', 'Ready', 'Picked Up', 'Out for Delivery'}


def paise(value):
    try:
        amount = Decimal(str(value)) * 100
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Invalid monetary amount') from None
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value() or amount > 99999999900:
        raise ValueError('Amounts must be nonnegative INR with at most two decimal places')
    return int(amount)


def rupees(value):
    if type(value) is not int or value < 0:
        raise ValueError('Expected nonnegative integer paise')
    return f'{value // 100}.{value % 100:02d}'


def percentage(value, basis_points):
    if type(value) is not int or value < 0 or type(basis_points) is not int or not 0 <= basis_points <= 10000:
        raise ValueError('Invalid percentage calculation')
    return (value * basis_points + 5000) // 10000


def allocation(paid, fee, kind):
    if any(type(x) is not int or x < 0 for x in (paid, fee)):
        raise ValueError('Expected integer paise')
    if kind not in {'Customer before preparing', 'Shop cancellation', 'Approved customer request'}:
        raise ValueError('Unknown cancellation policy')
    compensation = paid - percentage(paid, 8500) if kind == 'Approved customer request' else 0
    refund = (max(0, paid - fee) if kind == 'Customer before preparing'
              else paid - compensation)
    # A high fee cannot reduce the promised 85%/100% refund. Excess is shop debt.
    shop_debt = (max(0, fee - compensation) if kind != 'Customer before preparing'
                 else max(0, fee - paid))
    return dict(paid_paise=paid, gateway_fee_paise=fee, refund_paise=refund,
                compensation_paise=compensation, vendor_paise=max(0, compensation - fee),
                shop_debt_paise=shop_debt, commission_paise=0)


def fee_evidence(payload, order_id, payment_id, paid):
    if not isinstance(payload, dict) or payload.get('cursor') or not isinstance(payload.get('data'), list):
        raise ValueError('Complete Cashfree reconciliation evidence is required')
    rows = [r for r in payload['data'] if r.get('merchant_order_id') == order_id
            and r.get('entity_type') == 'transaction' and str(r.get('entity_id')) == str(payment_id)]
    if len(rows) != 1:
        raise ValueError('Actual gateway fee is not available yet')
    row = rows[0]
    if row.get('currency') != 'INR' or row.get('sale_type') != 'CREDIT' or paise(row['amount']) != paid:
        raise ValueError('Gateway charge evidence does not match the payment')
    # Missing charges are unknown, not zero. Keep tax separate in the evidence.
    fee = paise(row['pg_service_charge'])
    tax = paise(row['pg_service_tax'])
    split_fee = paise(row['split_service_charge'])
    split_tax = paise(row['split_service_tax'])
    return dict(fee_paise=fee, tax_paise=tax, split_fee_paise=split_fee,
                split_tax_paise=split_tax, total_paise=fee + tax + split_fee + split_tax)


def delivery_allocation(total, base=None, gst_bps=0, inclusive=False, retained_gst=0):
    """7% normal-order commission; preserve the configured GST basis and treatment."""
    base = total if base is None else base
    if any(type(v) is not int or v < 0 for v in (total, base, retained_gst)) or base > total or retained_gst > total:
        raise ValueError('Invalid delivery allocation')
    if type(gst_bps) is not int or not 0 <= gst_bps <= 10000:
        raise ValueError('Invalid GST rate')
    agreed = percentage(base, 700)
    net = (agreed * 10000 + (10000 + gst_bps) // 2) // (10000 + gst_bps) if inclusive else agreed
    tax = agreed - net if inclusive else percentage(net, gst_bps)
    gross = net + tax
    vendor = total - gross - retained_gst
    if vendor <= 0:
        raise ValueError('Charges leave no vendor settlement')
    return dict(total_paise=total, commission_paise=net, commission_gst_paise=tax,
                commission_gross_paise=gross, retained_gst_paise=retained_gst, vendor_paise=vendor)
