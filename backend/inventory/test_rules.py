"""Pure rules of the inventory: codes (RN-15), transitions (RN-01) and areas (RN-02)."""

import pytest

from .codes import (
    format_code,
    luhn_digit,
    next_warehouse_code,
    parse_code,
    warehouse_code_prefix,
)
from .states import (
    AREA_STATUSES,
    TRANSITIONS,
    AreaType,
    AssetStatus,
    DomainError,
    area_accepts,
    can_transition,
    check_area,
    check_transition,
)

S = AssetStatus


# --- Codes (RN-15) -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("digits", "check"),
    [("7992739871", "3"), ("00001234", "4"), ("00000001", "8"), ("12345678", "2")],
)
def test_luhn_digit(digits, check):
    assert luhn_digit(digits) == check


def test_format_code():
    assert format_code("H", 1234) == "H000012344"
    assert format_code("C", 1) == "C000000018"
    with pytest.raises(ValueError):
        format_code("H", 0)
    with pytest.raises(ValueError):
        format_code("H", 10**8)


def test_parse_code_checks_the_digit():
    good = parse_code(" h00001234 4 ")  # what a person might type
    assert (good.kind, good.code, good.number, good.valid) == ("asset", "H000012344", 1234, True)
    bad = parse_code("H000012345")
    assert (bad.kind, bad.valid) == ("asset", False)
    assert parse_code("C000000018").kind == "container"
    assert parse_code("C000000018").valid
    # Every single-digit error is caught
    code = format_code("H", 98765432)
    for position in range(1, len(code)):
        for digit in "0123456789":
            if digit != code[position]:
                typo = code[:position] + digit + code[position + 1 :]
                assert not parse_code(typo).valid, typo


def test_parse_code_locations_and_unknown():
    assert parse_code("sp01-est-03").kind == "location"
    assert parse_code("SP01-EST-03").code == "SP01-EST-03"
    unknown = parse_code("ABC")
    assert (unknown.kind, unknown.valid) == ("unknown", False)


@pytest.mark.parametrize(
    ("state", "country", "prefix"),
    [("SP", "BR", "SP"), ("", "BR", "BR"), ("", "us", "US"), ("n.y.", "US", "NY"), ("", "", "WH")],
)
def test_warehouse_code_prefix(state, country, prefix):
    assert warehouse_code_prefix(state, country) == prefix


def test_next_warehouse_code():
    assert next_warehouse_code("SP", set()) == "SP01"
    assert next_warehouse_code("SP", {"SP01", "SP03"}) == "SP02"
    assert next_warehouse_code("SP", {f"SP{n:02d}" for n in range(1, 100)}) == "SP100"


# --- Transitions (RN-01) ---------------------------------------------------------------------

ALLOWED = {
    (S.IN_TRIAGE, S.AWAITING_INSPECTION),
    (S.AWAITING_INSPECTION, S.IN_INSPECTION),
    (S.IN_INSPECTION, S.AVAILABLE),
    (S.IN_INSPECTION, S.BLOCKED),
    (S.IN_INSPECTION, S.SCRAP),
    (S.BLOCKED, S.IN_INSPECTION),
    (S.BLOCKED, S.SCRAP),
    (S.BLOCKED, S.AVAILABLE),
    (S.AVAILABLE, S.RESERVED),
    (S.AVAILABLE, S.SCRAP),
    (S.AVAILABLE, S.BLOCKED),
    (S.RESERVED, S.AVAILABLE),
    (S.RESERVED, S.WRITTEN_OFF),
    (S.SCRAP, S.WRITTEN_OFF),
}


@pytest.mark.parametrize("before", S.values)
@pytest.mark.parametrize("after", [s for s in S.values if s != S.IN_TRANSIT])
def test_every_transition_follows_the_table(before, after):
    if before == S.IN_TRANSIT:
        return  # covered below
    expected = (before, after) in ALLOWED
    assert can_transition(before, after) is expected
    if not expected:
        with pytest.raises(DomainError):
            check_transition(before, after)


def test_the_table_is_the_spec():
    table = {(before, after) for before, afters in TRANSITIONS.items() for after in afters}
    assert table == ALLOWED


def test_in_transit_and_back_to_the_previous_status():
    for status in S.values:
        assert can_transition(status, S.IN_TRANSIT) is (status not in (S.WRITTEN_OFF, S.IN_TRANSIT))
    assert can_transition(S.IN_TRANSIT, S.AVAILABLE, status_before_transit=S.AVAILABLE)
    assert not can_transition(S.IN_TRANSIT, S.RESERVED, status_before_transit=S.AVAILABLE)
    assert not can_transition(S.IN_TRANSIT, S.AVAILABLE)


def test_written_off_is_final():
    assert not any(can_transition(S.WRITTEN_OFF, after) for after in S.values)


# --- Areas (RN-02) -----------------------------------------------------------------------------


def test_area_table():
    assert AREA_STATUSES[AreaType.DOCK] == {S.IN_TRIAGE}
    assert AREA_STATUSES[AreaType.STOCK] == {S.AVAILABLE, S.RESERVED}
    assert AREA_STATUSES[AreaType.SHIPPING] == {S.RESERVED, S.SCRAP}
    assert set(AREA_STATUSES) == set(AreaType.values)


def test_area_accepts():
    assert area_accepts(AreaType.STOCK, S.AVAILABLE)
    assert not area_accepts(AreaType.STOCK, S.IN_TRIAGE)
    with pytest.raises(DomainError):
        check_area(AreaType.DOCK, S.AVAILABLE)
    # Quarantine also takes any asset held for a dispute
    assert not area_accepts(AreaType.QUARANTINE, S.AVAILABLE)
    assert area_accepts(AreaType.QUARANTINE, S.AVAILABLE, held_for_dispute=True)
