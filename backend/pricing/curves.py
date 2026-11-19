"""Market value curves for average prices. Pure functions (no database), fully tested.

A price row has an original value (month 0 = 100%) and anchor terms (e.g. 12, 24, 36 months),
each entered as a fixed value or as a percentage of the original value. Every month between two
anchors is a straight line between them:

    value(m) = value(a) + (value(b) - value(a)) / (b - a) * (m - a)      for a < m < b

e.g. original 100,000; 12 months = 70,000; 24 months = 55,000 → month 13 = 68,750.
The curve starts at month 0 (the original value) and stops at the last anchor.
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from typing import NamedTuple

CENTS = Decimal("0.01")
HUNDRED = Decimal("100")


class CurvePoint(NamedTuple):
    month: int
    value: Decimal  # money, 2 places
    percent: Decimal  # of the original value, 2 places
    is_anchor: bool  # entered by the user (or month 0), not interpolated


def money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def percent_of(original: Decimal, value: Decimal) -> Decimal:
    """`value` as a percentage of `original`, 2 places."""
    return (value / original * HUNDRED).quantize(CENTS, rounding=ROUND_HALF_UP)


def anchor_value(original: Decimal, mode: str, amount: Decimal) -> Decimal:
    """The money value of an anchor entered as a fixed value or as a % of the original."""
    if mode == "percent":
        return money(original * amount / HUNDRED)
    if mode == "value":
        return money(amount)
    raise ValueError(f"Unknown anchor mode: {mode!r}")


def monthly_curve(original: Decimal, anchors: Mapping[int, Decimal]) -> list[CurvePoint]:
    """Value of every month from 0 to the last anchor, by linear interpolation.

    `anchors` maps term in months (> 0) to its money value. Intermediate months are computed
    with full precision and rounded to cents only at the end, so rounding never accumulates.
    """
    if original <= 0:
        raise ValueError("The original value must be positive.")
    if any(term <= 0 for term in anchors):
        raise ValueError("Anchor terms must be positive.")

    points = {0: original, **anchors}
    terms = sorted(points)
    curve = []
    for start, end in pairwise(terms):
        start_value, end_value = points[start], points[end]
        step = (end_value - start_value) / (end - start)
        for month in range(start, end):
            value = money(start_value + step * (month - start))
            curve.append(CurvePoint(month, value, percent_of(original, value), month == start))
    last = terms[-1]
    last_value = money(points[last])
    curve.append(CurvePoint(last, last_value, percent_of(original, last_value), True))
    return curve


def increasing_terms(original: Decimal, anchors: Mapping[int, Decimal]) -> list[int]:
    """Anchor terms worth more than the point before them (unusual: the user is warned).

    The first anchor is compared with the original value (month 0).
    """
    terms = sorted(anchors)
    previous = original
    found = []
    for term in terms:
        if anchors[term] > previous:
            found.append(term)
        previous = anchors[term]
    return found
