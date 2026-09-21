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


BATCH_STAGES = ["Accepted", "Preparing", "Ready", "Picked Up", "Out for Delivery", "Delivered"]


def batch_transition(rows, target):
    """Advance one stage; skip already advanced orders to make retries safe."""
    if target not in BATCH_STAGES[1:-1]:
        raise ValueError("Accept requests and confirm customer deliveries individually")
    source_index = BATCH_STAGES.index(target) - 1
    pending = []
    for row in rows:
        status = row["status"]
        if status == "Cancelled":
            continue
        if status not in BATCH_STAGES or BATCH_STAGES.index(status) < source_index:
            raise ValueError(
                "Every active order must reach "
                + BATCH_STAGES[source_index]
                + " before this batch action"
            )
        if status == BATCH_STAGES[source_index]:
            pending.append(row["name"])
    return pending
