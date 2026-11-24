"""Inspection rules (pure): suggested grade, recommended destination, penalty periods."""

from datetime import date

import pytest

from .grades import (
    periods_overlap,
    recommended_destination,
    suggest_completeness,
    suggest_functioning,
)

SCRIPT = ["Boots", "Keyboard", "Battery"]
KIT = [
    {"item": "Charger", "essential": False},
    {"item": "Battery", "essential": True},
]


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ({}, ""),
        ({"Boots": "pass", "Keyboard": "pass"}, ""),  # one unanswered
        ({"Boots": "pass", "Keyboard": "na", "Battery": "pass"}, "1"),
        ({"Boots": "pass", "Keyboard": "fail", "Battery": "pass"}, "2"),
    ],
)
def test_suggest_functioning(results, expected):
    assert suggest_functioning(SCRIPT, results) == expected


def test_no_script_leaves_it_to_the_technician():
    assert suggest_functioning([], {}) == ""


@pytest.mark.parametrize(
    ("missing", "expected"),
    [([], "C"), (["charger"], "P"), (["Battery"], "I"), (["Charger", "Battery"], "I")],
)
def test_suggest_completeness(missing, expected):
    assert suggest_completeness(KIT, missing) == expected


@pytest.mark.parametrize(
    ("kinds", "functioning", "irreparable", "expected"),
    [
        (["access_block", "damage"], "1", False, "blocked"),
        (["access_block"], "3", True, "blocked"),
        ([], "3", True, "scrap"),
        ([], "3", False, "available"),
        (["missing_item"], "2", False, "available"),
    ],
)
def test_recommended_destination(kinds, functioning, irreparable, expected):
    assert recommended_destination(kinds, functioning, irreparable) == expected


@pytest.mark.parametrize(
    ("a", "b", "overlap"),
    [
        ((date(2026, 1, 1), date(2026, 6, 30)), (date(2026, 7, 1), None), False),
        ((date(2026, 1, 1), date(2026, 7, 1)), (date(2026, 7, 1), None), True),
        ((date(2026, 1, 1), None), (date(2027, 1, 1), date(2027, 2, 1)), True),
        ((date(2026, 3, 1), date(2026, 3, 31)), (date(2026, 1, 1), date(2026, 2, 28)), False),
    ],
)
def test_periods_overlap(a, b, overlap):
    assert periods_overlap(*a, *b) is overlap
    assert periods_overlap(*b, *a) is overlap
