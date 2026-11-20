"""How a price typed in an analysis compares with Average Prices, and whether an average price
is still current. Pure functions (no database), fully tested; the limits come from the
Pricing control panel (PricingSettings)."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import NamedTuple

CENTS = Decimal("0.01")
HUNDRED = Decimal("100")


class Position(StrEnum):
    BELOW = "below"
    SLIGHTLY_BELOW = "slightly_below"
    COMPATIBLE = "compatible"
    SLIGHTLY_ABOVE = "slightly_above"
    ABOVE = "above"


class PositionLimits(NamedTuple):
    """Percentages of the reference value."""

    compatible: Decimal  # at most this far (either way) = compatible
    below: Decimal  # this much below or more = below
    above: Decimal  # this much above or more = above


def variation_percent(entered: Decimal, reference: Decimal) -> Decimal:
    """How far the typed price is from the reference, in % of the reference (2 places,
    negative = below)."""
    return ((entered - reference) / reference * HUNDRED).quantize(CENTS, rounding=ROUND_HALF_UP)


def price_position(entered: Decimal, reference: Decimal, limits: PositionLimits) -> Position:
    """Below / slightly below / compatible / slightly above / above the historical value. The
    limits are inclusive (exactly 10% below with a 10% limit is below)."""
    variation = variation_percent(entered, reference)
    if variation <= -limits.below:
        return Position.BELOW
    if variation >= limits.above:
        return Position.ABOVE
    if abs(variation) <= limits.compatible:
        return Position.COMPATIBLE
    return Position.SLIGHTLY_BELOW if variation < 0 else Position.SLIGHTLY_ABOVE


def add_months(day: date, months: int) -> date:
    """Same day `months` later (the last day of the month when it does not exist there)."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    for last in (31, 30, 29, 28):
        try:
            return day.replace(year=year, month=month, day=min(day.day, last))
        except ValueError:
            continue
    raise AssertionError("unreachable")


def valid_until(priced_on: date | datetime, validity_months: int) -> date:
    if isinstance(priced_on, datetime):
        priced_on = priced_on.date()
    return add_months(priced_on, validity_months)


def is_expired(priced_on: date | datetime, today: date, validity_months: int) -> bool:
    """An average price expires `validity_months` after the date of its current version."""
    return today > valid_until(priced_on, validity_months)
