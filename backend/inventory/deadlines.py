"""Deadlines (pure, tested): a number of calendar or business days from a date. Business days
skip Saturdays, Sundays and the registered holidays."""

from datetime import date, timedelta


def is_business_day(day: date, holidays: set[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def add_days(start: date, days: int, *, business: bool, holidays: set[date] | None = None) -> date:
    """The last day of a deadline of `days` days counted from the day after `start`."""
    if not business:
        return start + timedelta(days=days)
    holidays = holidays or set()
    day, counted = start, 0
    while counted < days:
        day += timedelta(days=1)
        if is_business_day(day, holidays):
            counted += 1
    return day


def days_left(today: date, due: date) -> int:
    """Calendar days until the due date (0 on the day, negative after)."""
    return (due - today).days
