"""Reconciliation of a lot (pure) and pasted expected lists (pure)."""

from .expected import model_key, parse_pasted
from .reconciliation import Expected, Finding, ReceivedUnit, reconcile

NOTEBOOK, MONITOR, CABLE = 1, 2, 3


def _kinds(findings):
    return sorted(
        (f.kind, f.model_id, f.quantity, f.expected_serial, f.received_serial) for f in findings
    )


def test_unscheduled_lot_has_nothing_to_reconcile():
    assert reconcile([], [ReceivedUnit(1, NOTEBOOK, "A")], {CABLE: 5}, {CABLE}) == []


def test_everything_as_expected():
    expected = [Expected(NOTEBOOK, "a1"), Expected(NOTEBOOK, "A2"), Expected(MONITOR, quantity=2)]
    units = [
        ReceivedUnit(1, NOTEBOOK, "A1"),
        ReceivedUnit(2, NOTEBOOK, "a 2"),
        ReceivedUnit(3, MONITOR, "M9"),
        ReceivedUnit(4, MONITOR, ""),
    ]
    assert reconcile(expected, units, {}, set()) == []


def test_shortage_and_surplus_by_serial():
    expected = [Expected(NOTEBOOK, "A1"), Expected(NOTEBOOK, "A2")]
    units = [ReceivedUnit(1, NOTEBOOK, "A1"), ReceivedUnit(2, MONITOR, "M1")]
    assert _kinds(reconcile(expected, units, {}, set())) == [
        ("shortage", NOTEBOOK, 1, "A2", ""),
        ("surplus", MONITOR, 1, "", "M1"),
    ]


def test_serial_mismatch_pairs_an_unexpected_serial_with_an_open_line():
    expected = [Expected(NOTEBOOK, "A1"), Expected(NOTEBOOK, "A2")]
    units = [ReceivedUnit(1, NOTEBOOK, "A1"), ReceivedUnit(2, NOTEBOOK, "ZZ")]
    findings = reconcile(expected, units, {}, set())
    assert findings == [Finding("serial_mismatch", NOTEBOOK, 1, "A2", "ZZ", 2)]


def test_model_mismatch_when_an_expected_serial_comes_as_another_model():
    expected = [Expected(NOTEBOOK, "S1")]
    units = [ReceivedUnit(7, MONITOR, "S1")]
    assert reconcile(expected, units, {}, set()) == [
        Finding("model_mismatch", MONITOR, 1, "S1", "S1", 7)
    ]


def test_units_without_serial_stand_for_expected_lines():
    """The serial is completed at inspection; meanwhile the unit counts for its model."""
    expected = [Expected(NOTEBOOK, "A1"), Expected(NOTEBOOK, quantity=1)]
    units = [ReceivedUnit(1, NOTEBOOK, ""), ReceivedUnit(2, NOTEBOOK, "")]
    assert reconcile(expected, units, {}, set()) == []
    # One more without serial is a surplus
    units.append(ReceivedUnit(3, NOTEBOOK, ""))
    assert _kinds(reconcile(expected, units, {}, set())) == [("surplus", NOTEBOOK, 1, "", "")]


def test_quantity_lines():
    expected = [Expected(MONITOR, quantity=3)]
    units = [ReceivedUnit(1, MONITOR, "M1")]
    assert _kinds(reconcile(expected, units, {}, set())) == [("shortage", MONITOR, 2, "", "")]


def test_accessories_compare_quantities():
    expected = [Expected(CABLE, quantity=10), Expected(NOTEBOOK, "A1")]
    units = [ReceivedUnit(1, NOTEBOOK, "A1")]
    assert _kinds(reconcile(expected, units, {CABLE: 8}, {CABLE})) == [
        ("shortage", CABLE, 2, "", "")
    ]
    assert _kinds(reconcile(expected, units, {CABLE: 12}, {CABLE})) == [
        ("surplus", CABLE, 2, "", "")
    ]
    assert reconcile(expected, units, {CABLE: 10}, {CABLE}) == []


# --- Pasted lists ----------------------------------------------------------------------------


def test_parse_pasted_from_a_spreadsheet():
    text = "Modelo\tSérie\tQuantidade\nDell  Latitude 5440\tabc 123\t\nUSB-C Cable\t\t10\n\nX;;0\n"
    rows = parse_pasted(text)
    assert [(r.line, r.model_text, r.serial, r.quantity) for r in rows] == [
        (2, "Dell Latitude 5440", "ABC123", 1),
        (3, "USB-C Cable", "", 10),
        (5, "X", "", None),
    ]


def test_parse_pasted_with_commas_and_no_header():
    rows = parse_pasted("Dell Latitude,S1\nDell Latitude,,2")
    assert [(r.model_text, r.serial, r.quantity) for r in rows] == [
        ("Dell Latitude", "S1", 1),
        ("Dell Latitude", "", 2),
    ]


def test_model_key():
    assert model_key("  Dell   LATITUDE 5440 ") == "dell latitude 5440"
