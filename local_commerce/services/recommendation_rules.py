"""Small, explainable purchase-frequency model with weekday and recency weights."""

from collections import defaultdict


def rank_products(purchases, today):
    scores = defaultdict(float)
    seen = set()
    for row in purchases:
        purchased = row["purchased_on"]
        age = (today - purchased).days
        if age < 0 or age > 180:
            continue
        # Count an item once per order, independent of pack size or quantity.
        key = (row["order"], row["item"])
        if key in seen:
            continue
        seen.add(key)
        recency = 0.5 ** (age / 60)
        weekday = 2 if purchased.weekday() == today.weekday() else 1
        scores[row["item"]] += recency * weekday
    return sorted(scores, key=lambda item: (-scores[item], item))
