"""Delivery windows and a deterministic nearest-road-stop heuristic."""

from datetime import datetime
from math import isfinite


def window(start, close, delivery, end):
    values = [datetime.fromisoformat(str(v)) for v in (start, close, delivery, end)]
    if not values[0] < values[1] <= values[2] < values[3]:
        raise ValueError("Use ordering start < ordering end <= delivery start < delivery end")
    return values


def nearest_stops(matrix):
    size = len(matrix)
    if size < 2 or any(len(row) != size for row in matrix):
        raise ValueError("Invalid road travel-time matrix")
    pending, result, current = set(range(1, size)), [], 0
    while pending:
        reachable = [
            i
            for i in pending
            if matrix[current][i] is not None
            and isfinite(float(matrix[current][i]))
            and matrix[current][i] >= 0
        ]
        if not reachable:
            raise ValueError("Some delivery stops cannot be reached by road")
        current = min(reachable, key=lambda i: (matrix[current][i], i))
        result.append(current - 1)
        pending.remove(current)
    return result
