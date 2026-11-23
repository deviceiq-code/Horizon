"""Calculations of eFMV analyses. Pure functions (no database), fully tested.

Per scenario:
- LO (Leasing Origination): the total value of its items, quantity × unit value (typed by the
  analyst; Average Prices only position it, see pricing/positioning.py).
- HW / SW / SV: the share of hardware, software and services in the LO (5 decimal places).
  Assets from Average Prices are hardware; software and services come later.
- eFMV at the end of the lease (EOL): the eFMV of the items weighted over the LO —
  Σ quantity × eFMV value (one unit at the end of the term) / LO, as a percentage with 2
  decimal places.
- Weight of an item: its total (quantity × unit value) as a percentage of the LO, 5 places.
- Services (SV) of an item: per unit, the item's quantity; added on top of the asset's value or
  deducted from it (the asset is then worth the rest: `split_service`); never worth more than
  the asset. Their eFMV is 0, so
  they lower the eFMV at EOL.
"""

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, NamedTuple

from config.decimals import percent

CENTS = Decimal("0.01")
HUNDRED = Decimal("100")

Category = Literal["hw", "sw", "sv"]


class Line(NamedTuple):
    category: Category
    quantity: int
    unit_value: Decimal
    # One unit at the end of the term; None counts as nothing left
    efmv_value: Decimal | None = None


class ScenarioTotals(NamedTuple):
    lo: Decimal  # money, 2 places
    efmv_total: Decimal  # money at the end of the term, 2 places
    efmv_percent: Decimal | None  # of the LO, 5 places; None without any value
    hw_percent: Decimal | None  # of the LO, 5 places; None without any value
    sw_percent: Decimal | None
    sv_percent: Decimal | None
    # How much of the LO each kind is, in money (2 places)
    hw_total: Decimal = Decimal("0.00")
    sw_total: Decimal = Decimal("0.00")
    sv_total: Decimal = Decimal("0.00")


def line_total(quantity: int, unit_value: Decimal) -> Decimal:
    return (unit_value * quantity).quantize(CENTS, rounding=ROUND_HALF_UP)


def scenario_totals(lines: Iterable[Line]) -> ScenarioTotals:
    by_category = {"hw": Decimal(0), "sw": Decimal(0), "sv": Decimal(0)}
    efmv = Decimal(0)
    for line in lines:
        by_category[line.category] += line.unit_value * line.quantity
        if line.efmv_value is not None:
            efmv += line.efmv_value * line.quantity
    lo = sum(by_category.values(), Decimal(0))

    def of_lo(amount: Decimal) -> Decimal | None:
        if lo == 0:
            return None
        return percent(amount / lo * HUNDRED)

    def share(category: Category) -> Decimal | None:
        return of_lo(by_category[category])

    return ScenarioTotals(
        lo=lo.quantize(CENTS, rounding=ROUND_HALF_UP),
        efmv_total=efmv.quantize(CENTS, rounding=ROUND_HALF_UP),
        efmv_percent=of_lo(efmv),
        hw_percent=share("hw"),
        sw_percent=share("sw"),
        sv_percent=share("sv"),
        hw_total=by_category["hw"].quantize(CENTS, rounding=ROUND_HALF_UP),
        sw_total=by_category["sw"].quantize(CENTS, rounding=ROUND_HALF_UP),
        sv_total=by_category["sv"].quantize(CENTS, rounding=ROUND_HALF_UP),
    )


def weight_percent(quantity: int, unit_value: Decimal, lo: Decimal) -> Decimal | None:
    """How much of the scenario's LO one item is (%, 5 places); None without LO."""
    if lo == 0:
        return None
    return percent(unit_value * quantity / lo * HUNDRED)


def efmv_percent_of_unit(efmv_value: Decimal, unit_value: Decimal) -> Decimal | None:
    """An item's eFMV as a percentage of its unit value (5 places); None without a value."""
    if unit_value == 0:
        return None
    return percent(efmv_value / unit_value * HUNDRED)


def percent_of_value(value: Decimal, percent: Decimal) -> Decimal:
    """`percent` % of `value`, in money (2 places, half up): an eFMV typed as a percentage
    of the unit value ("25%" of 100.00 → 25.00)."""
    return (value * percent / HUNDRED).quantize(CENTS, rounding=ROUND_HALF_UP)


def split_service(
    unit_value: Decimal, service_value: Decimal, deduct: bool
) -> tuple[Decimal, Decimal] | None:
    """(asset's unit value, service's unit value) of an item with a service. Deducted, the
    service comes out of the value typed for the asset. None when the service is worth more
    than the asset or, deducted, when it would leave the asset with nothing."""
    if service_value > unit_value:
        return None
    if not deduct:
        return unit_value, service_value
    rest = unit_value - service_value
    return (rest, service_value) if rest >= CENTS else None


def covers_term(anchor_terms: Sequence[int], term_months: int) -> bool:
    """Whether an asset's value curve reaches the scenario's term (the curve stops at its last
    term)."""
    return bool(anchor_terms) and 1 <= term_months <= max(anchor_terms)
