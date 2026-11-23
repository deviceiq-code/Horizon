"""Precision of the system's figures: money with 2 decimal places (cents) and percentages with
5 — the server always calculates percentages with 5 places; how many are shown is each user's
preference (`UserPreferences.percent_places`, 1–5). Half up."""

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
PERCENT_PLACES = 5
PERCENT_QUANTUM = Decimal("0.00001")


def money(value: Decimal) -> Decimal:
    """Money: 2 places, half up."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def percent(value: Decimal) -> Decimal:
    """A percentage: 5 places, half up."""
    return value.quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)
