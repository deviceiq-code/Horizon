from decimal import Decimal as D

from efmv.calculations import Line, covers_term, line_total, scenario_totals


def test_line_total_rounds_half_up():
    assert line_total(3, D("0.335")) == D("1.01")
    assert line_total(2, D("100000.00")) == D("200000.00")


def test_totals_hardware_only():
    totals = scenario_totals([Line("hw", 2, D("100000")), Line("hw", 1, D("50000.50"))])
    assert totals.lo == D("250000.50")
    assert totals.hw_percent == D("100.00")
    assert totals.sw_percent == D("0.00")
    assert totals.sv_percent == D("0.00")


def test_totals_shares_with_two_places():
    totals = scenario_totals([Line("hw", 1, D("1")), Line("sw", 1, D("1")), Line("sv", 1, D("1"))])
    assert (totals.hw_percent, totals.sw_percent, totals.sv_percent) == (
        D("33.33"),
        D("33.33"),
        D("33.33"),
    )
    totals = scenario_totals([Line("hw", 2, D("1")), Line("sw", 1, D("1"))])
    assert (totals.hw_percent, totals.sw_percent) == (D("66.67"), D("33.33"))


def test_totals_without_lines():
    totals = scenario_totals([])
    assert totals.lo == D("0.00")
    assert totals.hw_percent is None


def test_covers_term():
    assert covers_term([12, 24, 36], 36)
    assert covers_term([12, 24, 36], 30)
    assert not covers_term([12, 24, 36], 37)
    assert not covers_term([], 12)
