"""Weekly shop ordering availability in the site timezone."""

import json
from datetime import datetime, timedelta

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def normalize(value):
    if not value:
        return []
    rows = json.loads(value) if isinstance(value, str) else value
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError("Set opening hours for all seven days")
    result = []
    for index, day in enumerate(DAYS):
        row = rows[index]
        if not isinstance(row, dict) or row.get("day") != day:
            raise ValueError("Opening-hour days are invalid")
        enabled = bool(row.get("enabled"))
        opens = str(row.get("opens") or "09:00")
        closes = str(row.get("closes") or "21:00")
        for value_to_check in (opens, closes):
            try:
                datetime.strptime(value_to_check, "%H:%M")
            except ValueError as exc:
                raise ValueError("Opening hours must use a valid time") from exc
        if enabled and opens == closes:
            raise ValueError(f"{day} opening and closing times must differ")
        result.append({"day": day, "enabled": enabled, "opens": opens, "closes": closes})
    return result


def _minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def availability(doc, current=None):
    if current is None:
        from frappe.utils import now_datetime

        current = now_datetime()
    if not doc.accepting_orders:
        return {"open": False, "label": "Paused", "message": "The shop paused new orders"}
    schedule = normalize(doc.opening_hours_json)
    if not schedule:
        return {"open": True, "label": "Open", "message": "Open for orders"}
    now_minutes = current.hour * 60 + current.minute
    today = current.weekday()
    row = schedule[today]
    if row["enabled"]:
        opens, closes = _minutes(row["opens"]), _minutes(row["closes"])
        open_now = opens <= now_minutes < closes if opens < closes else now_minutes >= opens
        if open_now:
            remaining = (closes - now_minutes) % (24 * 60)
            return {
                "open": True,
                "label": "Closing soon" if remaining <= 30 else "Open",
                "message": f"Closes at {row['closes']}",
            }
    previous = schedule[(today - 1) % 7]
    if previous["enabled"] and _minutes(previous["opens"]) > _minutes(previous["closes"]):
        if now_minutes < _minutes(previous["closes"]):
            return {"open": True, "label": "Open", "message": f"Closes at {previous['closes']}"}
    for offset in range(0, 8):
        candidate = schedule[(today + offset) % 7]
        if not candidate["enabled"]:
            continue
        opening = current.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=offset, minutes=_minutes(candidate["opens"])
        )
        if opening > current:
            day_label = "today" if offset == 0 else "tomorrow" if offset == 1 else candidate["day"]
            return {
                "open": False,
                "label": "Closed",
                "message": f"Opens {day_label} at {candidate['opens']}",
            }
    return {"open": False, "label": "Closed", "message": "Opening time unavailable"}
