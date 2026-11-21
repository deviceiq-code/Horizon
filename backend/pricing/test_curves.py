from decimal import Decimal as D

import pytest

from .curves import anchor_value, increasing_terms, monthly_curve, percent_of, value_at


def test_example_from_the_specification():
    # (month 13) = (month 12) + ((month 24) - (month 12)) / (24 - 12) * (13 - 12)
    curve = monthly_curve(D("100000"), {12: D("70000"), 24: D("55000")})
    by_month = {p.month: p for p in curve}
    assert by_month[13].value == D("68750.00")
    assert by_month[13].percent == D("68.75")
    assert by_month[18].value == D("62500.00")
    assert by_month[24].value == D("55000.00")


def test_starts_at_month_zero_with_the_original_value():
    curve = monthly_curve(D("100000"), {12: D("70000")})
    assert curve[0].month == 0
    assert curve[0].value == D("100000.00")
    assert curve[0].percent == D("100.00")
    # Months 1–11 go from 100% down to the 12-month anchor
    assert curve[6].value == D("85000.00")


def test_stops_at_the_last_anchor():
    curve = monthly_curve(D("1000"), {12: D("800"), 24: D("600"), 36: D("500")})
    assert [p.month for p in curve] == list(range(0, 37))
    assert curve[-1].month == 36


def test_anchors_are_flagged_and_kept_exactly():
    anchors = {12: D("800"), 24: D("600")}
    curve = monthly_curve(D("1000"), anchors)
    flagged = [p.month for p in curve if p.is_anchor]
    assert flagged == [0, 12, 24]
    assert {p.month: p.value for p in curve if p.month in anchors} == anchors


def test_rounding_happens_per_month_without_accumulating():
    # 100 → 0 over 3 months: 66.666… and 33.333… round to cents independently
    curve = monthly_curve(D("100"), {3: D("0")})
    assert [p.value for p in curve] == [D("100.00"), D("66.67"), D("33.33"), D("0.00")]


def test_anchor_order_does_not_matter():
    a = monthly_curve(D("1000"), {24: D("600"), 12: D("800")})
    b = monthly_curve(D("1000"), {12: D("800"), 24: D("600")})
    assert a == b


def test_curve_may_go_up_between_anchors():
    curve = monthly_curve(D("1000"), {12: D("600"), 24: D("700")})
    assert curve[18].value == D("650.00")


@pytest.mark.parametrize(
    ("original", "anchors"),
    [(D("0"), {12: D("1")}), (D("-1"), {12: D("1")}), (D("1000"), {0: D("1")})],
)
def test_invalid_input(original, anchors):
    with pytest.raises(ValueError):
        monthly_curve(original, anchors)


@pytest.mark.parametrize(
    ("mode", "amount", "expected"),
    [
        ("percent", D("70"), D("70000.00")),
        ("percent", D("68.755"), D("68755.00")),
        ("percent", D("33.3333"), D("33333.30")),
        ("value", D("55000"), D("55000.00")),
        ("value", D("55000.005"), D("55000.01")),  # half up
    ],
)
def test_anchor_value(mode, amount, expected):
    assert anchor_value(D("100000"), mode, amount) == expected


def test_anchor_value_unknown_mode():
    with pytest.raises(ValueError):
        anchor_value(D("1"), "other", D("1"))


def test_percent_of():
    assert percent_of(D("150000"), D("100000")) == D("66.67")


def test_increasing_terms():
    original = D("1000")
    assert increasing_terms(original, {12: D("800"), 24: D("600")}) == []
    assert increasing_terms(original, {12: D("800"), 24: D("850"), 36: D("700")}) == [24]
    # The first anchor is compared with the original value
    assert increasing_terms(original, {12: D("1100")}) == [12]
    # Same value is not an increase
    assert increasing_terms(original, {12: D("800"), 24: D("800")}) == []


def test_value_at_a_month():
    anchors = {12: D("70000"), 24: D("55000")}
    assert value_at(D("100000"), anchors, 0) == D("100000.00")
    assert value_at(D("100000"), anchors, 13) == D("68750.00")
    assert value_at(D("100000"), anchors, 24) == D("55000.00")
    # Beyond the last term the curve does not exist
    assert value_at(D("100000"), anchors, 25) is None
    assert value_at(D("100000"), {}, 1) is None
