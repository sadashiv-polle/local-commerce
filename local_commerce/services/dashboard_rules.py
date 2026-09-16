from datetime import timedelta


def period_start(period, today):
    if period == "today":
        return today
    if period == "week":
        return today - timedelta(days=today.weekday())
    if period == "month":
        return today.replace(day=1)
    raise ValueError("Choose today, week or month")


