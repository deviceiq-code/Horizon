"""Remarketing ratings: 0–5 stars in half steps, and their average.

Pure functions (no database), so the rule is easy to test and reuse in future calculations.
"""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

STARS_MIN = Decimal("0")
STARS_MAX = Decimal("5")
_TWO_PLACES = Decimal("0.01")


def is_half_star(value: Decimal) -> bool:
    """True for whole or half stars (3, 3.5); False for 3.3."""
    return (value * 2) % 1 == 0


def average_stars(values: Iterable[Decimal | None]) -> Decimal:
    """Simple average of the ratings, rounded to 2 places (half up). Missing ones count as 0.

    >>> average_stars([Decimal("3.5"), Decimal("4"), Decimal("0"), Decimal("5")])
    Decimal('3.13')
    """
    stars = [value if value is not None else Decimal("0") for value in values]
    if not stars:
        return Decimal("0.00")
    return (sum(stars, Decimal("0")) / len(stars)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
