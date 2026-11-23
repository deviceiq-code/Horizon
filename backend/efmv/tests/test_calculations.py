from decimal import Decimal as D

from efmv.calculations import (
    Line,
    covers_term,
    efmv_percent_of_unit,
    line_total,
    percent_of_value,
    scenario_totals,
    split_service,
    weight_percent,
)


def test_line_total_rounds_half_up():
    assert line_total(3, D("0.335")) == D("1.01")
    assert line_total(2, D("100000.00")) == D("200000.00")


def test_totals_hardware_only():
    totals = scenario_totals([Line("hw", 2, D("100000")), Line("hw", 1, D("50000.50"))])
    assert totals.lo == D("250000.50")
    assert totals.hw_percent == D("100.00")
    assert totals.sw_percent == D("0.00")
    assert totals.sv_percent == D("0.00")


def test_totals_shares_with_five_places():
    totals = scenario_totals([Line("hw", 1, D("1")), Line("sw", 1, D("1")), Line("sv", 1, D("1"))])
    assert (totals.hw_percent, totals.sw_percent, totals.sv_percent) == (
        D("33.33333"),
        D("33.33333"),
        D("33.33333"),
    )
    totals = scenario_totals([Line("hw", 2, D("1")), Line("sw", 1, D("1"))])
    assert (totals.hw_percent, totals.sw_percent) == (D("66.66667"), D("33.33333"))


def test_totals_without_lines():
    totals = scenario_totals([])
    assert totals.lo == D("0.00")
    assert totals.hw_percent is None
    assert (totals.efmv_total, totals.efmv_percent) == (D("0.00"), None)


def test_efmv_weighted_over_the_lo():
    totals = scenario_totals(
        [Line("hw", 2, D("100000"), D("55000")), Line("hw", 1, D("50000"), D("30000"))]
    )
    assert totals.efmv_total == D("140000.00")
    assert totals.efmv_percent == D("56.00")
    # Zero at the end of the term counts as such; thirds round half up
    totals = scenario_totals([Line("hw", 1, D("3"), D("1")), Line("hw", 1, D("3"), D("0"))])
    assert totals.efmv_percent == D("16.66667")


def test_covers_term():
    assert covers_term([12, 24, 36], 36)
    assert covers_term([12, 24, 36], 30)
    assert not covers_term([12, 24, 36], 37)
    assert not covers_term([], 12)


def test_weight_of_an_item():
    assert weight_percent(2, D("100000"), D("250000")) == D("80.00")
    assert weight_percent(1, D("1"), D("3")) == D("33.33333")
    assert weight_percent(1, D("1"), D("0")) is None


def test_percent_of_a_value():
    assert percent_of_value(D("100.00"), D("25")) == D("25.00")
    assert percent_of_value(D("12371.91"), D("12.5")) == D("1546.49")  # 1546.48875
    assert percent_of_value(D("100"), D("0")) == D("0.00")


def test_efmv_as_a_percentage_of_the_unit_value():
    assert efmv_percent_of_unit(D("25.00"), D("100.00")) == D("25.00")
    assert efmv_percent_of_unit(D("55000"), D("100000")) == D("55.00")
    assert efmv_percent_of_unit(D("1"), D("3")) == D("33.33333")
    assert efmv_percent_of_unit(D("1"), D("0")) is None


def test_a_service_added_or_deducted():
    assert split_service(D("10000"), D("1000"), deduct=False) == (D("10000"), D("1000"))
    assert split_service(D("10000"), D("1000"), deduct=True) == (D("9000"), D("1000"))
    assert split_service(D("10000"), D("0"), deduct=True) == (D("10000"), D("0"))
    # Nothing would be left of the asset
    assert split_service(D("1000"), D("1000"), deduct=True) is None
    # Never worth more than the asset; added, it may be worth as much
    assert split_service(D("1000"), D("1000.01"), deduct=False) is None
    assert split_service(D("1000"), D("1000"), deduct=False) == (D("1000"), D("1000"))


def test_services_count_in_the_lo_but_not_in_the_efmv():
    # 2 × 10,000 (eFMV 4,000 each) and a warranty of 1,000 per unit on top
    totals = scenario_totals(
        [Line("hw", 2, D("10000"), D("4000")), Line("sv", 2, D("1000"), D("0"))]
    )
    assert totals.lo == D("22000.00")
    assert (totals.hw_percent, totals.sv_percent) == (D("90.90909"), D("9.09091"))
    # The same shares in money
    assert (totals.hw_total, totals.sw_total, totals.sv_total) == (
        D("20000.00"),
        D("0.00"),
        D("2000.00"),
    )
    # 8,000 of 22,000: lower than the 40% without the service
    assert totals.efmv_percent == D("36.36364")
