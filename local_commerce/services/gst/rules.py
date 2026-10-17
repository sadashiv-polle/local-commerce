"""Pure decimal calculations. Rates and registration are explicit admin decisions."""
import re
from decimal import Decimal
from local_commerce.services.payments.rules import money

MODES = ('Legacy', 'Exempt goods', 'Seller GST', 'Restaurant 9(5)')


def gstin(value):
    value = str(value or '').strip().upper()
    if not re.fullmatch(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]', value):
        raise ValueError('Enter a valid 15-character GSTIN')
    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    total, factor = 0, 2
    for char in reversed(value[:-1]):
        digit = alphabet.index(char) * factor
        total += digit // 36 + digit % 36
        factor = 1 if factor == 2 else 2
    if alphabet[(36 - total % 36) % 36] != value[-1]:
        raise ValueError('GSTIN checksum is invalid')
    return value


def amounts(base, delivery, tax, total, rate='7', gst_rate='18', inclusive=True, mode='Seller GST'):
    base, delivery, tax, total = map(money, (base, delivery, tax, total))
    rate, gst_rate = money(rate), money(gst_rate)
    if mode not in MODES[1:] or rate >= 100 or gst_rate > 100:
        raise ValueError('Invalid GST model or commission rate')
    if base + delivery + tax != total:
        raise ValueError('Order taxes, charges and total do not balance; review rounding')
    if mode == 'Exempt goods' and tax:
        raise ValueError('Exempt goods profile cannot contain tax; review the tax template')
    if mode == 'Restaurant 9(5)' and tax != money((base + delivery) * Decimal('0.05')):
        raise ValueError('Restaurant tax must be 5% of food and restaurant delivery charges')
    agreed = money(base * rate / 100)
    income = money(agreed / (1 + gst_rate / 100)) if inclusive else agreed
    commission_tax = agreed - income if inclusive else money(income * gst_rate / 100)
    gross = income + commission_tax
    eco = tax if mode == 'Restaurant 9(5)' else money(0)
    vendor = total - gross - eco
    if vendor <= 0:
        raise ValueError('Commission and retained GST leave no shop settlement')
    return {k: str(v) for k, v in dict(base=base, delivery=delivery, supply_tax=tax,
        total=total, commission_base=income, commission_tax=commission_tax,
        commission_gross=gross, eco_tax=eco, vendor_amount=vendor).items()}


def split_tax(value, interstate):
    value = money(value)
    if interstate:
        return {'igst': str(value), 'cgst': '0.00', 'sgst': '0.00'}
    cgst = money(value / 2)
    return {'igst': '0.00', 'cgst': str(cgst), 'sgst': str(value - cgst)}


def refund_parts(original, refunded_base, refunded_delivery, refunded_tax, previous):
    """Cumulative allocation avoids rounding drift over repeated partial refunds."""
    base, delivery, tax = map(money, (refunded_base, refunded_delivery, refunded_tax))
    for key, value in [('base', base), ('delivery', delivery), ('supply_tax', tax)]:
        if value > money(original[key]):
            raise ValueError('Refund exceeds the original taxable component')
    factor = base / money(original['base']) if money(original['base']) else Decimal(0)
    cumulative = {k: money(money(original[k]) * factor)
                  for k in ('commission_gross', 'commission_base')}
    cumulative['commission_tax'] = cumulative['commission_gross'] - cumulative['commission_base']
    cumulative['eco_tax'] = tax if money(original['eco_tax']) else money(0)
    cumulative.update(base=base, delivery=delivery, supply_tax=tax, total=base + delivery + tax)
    cumulative['vendor_amount'] = cumulative['total'] - cumulative['commission_gross'] - cumulative['eco_tax']
    result = {key: value - money(previous.get(key, 0)) for key, value in cumulative.items()}
    if any(value < 0 for value in result.values()):
        raise ValueError('Refund history changed or commission allocation decreased')
    return {key: str(value) for key, value in result.items()}
