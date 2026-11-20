from datetime import date
from decimal import Decimal as D

from pricing.positioning import (
    Position,
    PositionLimits,
    add_months,
    is_expired,
    price_position,
    valid_until,
    variation_percent,
)

LIMITS = PositionLimits(compatible=D("5"), below=D("10"), above=D("10"))


def test_variation():
    assert variation_percent(D("90"), D("100")) == D("-10.00")
    assert variation_percent(D("100"), D("120")) == D("-16.67")
    assert variation_percent(D("105.005"), D("100")) == D("5.01")


def test_positions_with_inclusive_limits():
    position = lambda value: price_position(D(value), D("100000"), LIMITS)  # noqa: E731
    assert position("90000") == Position.BELOW  # exactly 10% below
    assert position("85000") == Position.BELOW
    # Compared as shown (2 places): 9.999% below reads -10.00%, so it is below
    assert position("90001") == Position.BELOW
    assert position("90010") == Position.SLIGHTLY_BELOW
    assert position("95000") == Position.COMPATIBLE  # exactly 5%
    assert position("100000") == Position.COMPATIBLE
    assert position("105000") == Position.COMPATIBLE
    assert position("105010") == Position.SLIGHTLY_ABOVE
    assert position("110000") == Position.ABOVE
    assert position("250000") == Position.ABOVE


def test_asymmetric_limits():
    limits = PositionLimits(compatible=D("3"), below=D("15"), above=D("8"))
    assert price_position(D("90"), D("100"), limits) == Position.SLIGHTLY_BELOW
    assert price_position(D("108"), D("100"), limits) == Position.ABOVE
    assert price_position(D("97"), D("100"), limits) == Position.COMPATIBLE


def test_add_months_keeps_the_day_or_the_month_end():
    assert add_months(date(2026, 1, 15), 12) == date(2027, 1, 15)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2027, 12, 31), 2) == date(2028, 2, 29)
    assert add_months(date(2026, 11, 20), 14) == date(2028, 1, 20)


def test_expiry():
    assert valid_until(date(2025, 11, 20), 12) == date(2026, 11, 20)
    assert not is_expired(date(2025, 11, 20), date(2026, 11, 20), 12)  # last valid day
    assert is_expired(date(2025, 11, 20), date(2026, 11, 21), 12)
