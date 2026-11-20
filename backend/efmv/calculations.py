"""Calculations of eFMV analyses. Pure functions (no database), fully tested.

Per scenario:
- LO (Leasing Origination): the total value of its items, quantity × unit value (typed by the
  analyst; Average Prices only position it, see pricing/positioning.py).
- HW / SW / SV: the share of hardware, software and services in the LO (2 decimal places).
  Assets from Average Prices are hardware; software and services come later.
- eFMV at the end of the lease: to come (shown as a percentage, 2 decimal places).
"""

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, NamedTuple

CENTS = Decimal("0.01")
HUNDRED = Decimal("100")

Category = Literal["hw", "sw", "sv"]


class Line(NamedTuple):
    category: Category
    quantity: int
    unit_value: Decimal


class ScenarioTotals(NamedTuple):
    lo: Decimal  # money, 2 places
    hw_percent: Decimal | None  # of the LO, 2 places; None without any value
    sw_percent: Decimal | None
    sv_percent: Decimal | None


def line_total(quantity: int, unit_value: Decimal) -> Decimal:
    return (unit_value * quantity).quantize(CENTS, rounding=ROUND_HALF_UP)


def scenario_totals(lines: Iterable[Line]) -> ScenarioTotals:
    by_category = {"hw": Decimal(0), "sw": Decimal(0), "sv": Decimal(0)}
    for line in lines:
        by_category[line.category] += line.unit_value * line.quantity
    lo = sum(by_category.values(), Decimal(0))

    def share(category: Category) -> Decimal | None:
        if lo == 0:
            return None
        return (by_category[category] / lo * HUNDRED).quantize(CENTS, rounding=ROUND_HALF_UP)

    return ScenarioTotals(
        lo=lo.quantize(CENTS, rounding=ROUND_HALF_UP),
        hw_percent=share("hw"),
        sw_percent=share("sw"),
        sv_percent=share("sv"),
    )


def covers_term(anchor_terms: Sequence[int], term_months: int) -> bool:
    """Whether an asset's value curve reaches the scenario's term (the curve stops at its last
    term)."""
    return bool(anchor_terms) and 1 <= term_months <= max(anchor_terms)
