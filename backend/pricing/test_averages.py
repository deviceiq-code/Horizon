from decimal import Decimal as D

from .averages import AverageTerm, versions_average


def test_no_versions():
    assert versions_average([]) is None


def test_average_of_values_and_percentages():
    result = versions_average(
        [
            (D("100000"), {12: D("70000"), 24: D("55000")}),
            (D("120000"), {12: D("90000"), 24: D("60000")}),
        ]
    )
    assert result.count == 2
    assert result.original_value == D("110000.00")
    assert result.points == [
        # 70% and 75% → 72.50%
        AverageTerm(12, D("80000.00"), D("72.50"), 2),
        # 55% and 50% → 52.50%
        AverageTerm(24, D("57500.00"), D("52.50"), 2),
    ]


def test_terms_only_in_some_versions():
    result = versions_average(
        [
            (D("100000"), {12: D("70000")}),
            (D("100000"), {12: D("80000"), 36: D("40000")}),
        ]
    )
    assert result.points == [
        AverageTerm(12, D("75000.00"), D("75.00"), 2),
        AverageTerm(36, D("40000.00"), D("40.00"), 1),
    ]


def test_rounding_half_up():
    result = versions_average([(D("1.00"), {12: D("0.01")}), (D("1.00"), {12: D("0.02")})])
    assert result.points[0].value == D("0.02")  # 0.015 → 0.02
