"""Average of the versions of an average price (pure, tested).

Each version contributes its original value and its value at each term. The average of a term
uses only the versions that have it (terms come from the sub-vertical when each version was
created, so they may differ). The percentage is the average of each version's percentage.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import NamedTuple

from config.decimals import percent

from .curves import money, percent_of


class AverageTerm(NamedTuple):
    term_months: int
    value: Decimal  # money, 2 places
    percent: Decimal  # average of the versions' percentages, 5 places
    count: int  # versions that have this term


class VersionsAverage(NamedTuple):
    count: int
    original_value: Decimal
    points: list[AverageTerm]


def versions_average(
    versions: Sequence[tuple[Decimal, Mapping[int, Decimal]]],
) -> VersionsAverage | None:
    """`versions`: (original value, {term: value}) of each version. None when there are none."""
    if not versions:
        return None
    originals = [original for original, _ in versions]
    by_term: dict[int, list[tuple[Decimal, Decimal]]] = {}
    for original, anchors in versions:
        for term, value in anchors.items():
            by_term.setdefault(term, []).append((value, percent_of(original, value)))
    points = [
        AverageTerm(
            term_months=term,
            value=money(sum(v for v, _ in entries) / len(entries)),
            percent=percent(sum(p for _, p in entries) / len(entries)),
            count=len(entries),
        )
        for term, entries in sorted(by_term.items())
    ]
    return VersionsAverage(
        count=len(versions),
        original_value=money(sum(originals) / len(originals)),
        points=points,
    )
