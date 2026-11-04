"""Explicit product classification; never infer dietary suitability from names."""


def validate(value):
    if not isinstance(value, str) or value not in ('', 'Veg', 'Non-veg'):
        raise ValueError('Choose Veg, Non-veg, or Not specified')
    return value


def catalog_filter(value):
    return {'lc_food_type': validate(value)} if value != '' else {}
