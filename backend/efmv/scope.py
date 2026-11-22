"""The scope of a scenario, written from its assets (Smart Tools: automatic scope). Pure
functions, tested.

The assets are grouped by manufacturer and asset class (their units added up); groups with less
than `threshold` % of the units are left out (negligible). What is left is written from the
largest: a manufacturer's classes together ("Dell Laptops and Desktops"), manufacturers with
the same classes together ("Dell and Lenovo Laptops"), at most three such parts ("…, and other
assets"). Each language has its word order: "Dell Laptops" in English, "Laptops Dell" in
Portuguese and Spanish. Services are not part of it.
"""

from collections.abc import Iterable
from decimal import Decimal
from typing import NamedTuple


class ScopeGroup(NamedTuple):
    manufacturer: str
    asset_class: str  # its plural, in the language of the text
    quantity: int


class Wording(NamedTuple):
    conjunction: str
    others: str
    manufacturer_first: bool


WORDINGS = {
    "en": Wording("and", "other assets", manufacturer_first=True),
    "pt-br": Wording("e", "outros bens", manufacturer_first=False),
    "es": Wording("y", "otros bienes", manufacturer_first=False),
}
MAX_PARTS = 3


def join(words: list[str], conjunction: str) -> str:
    """ "A", "A and B", "A, B and C"."""
    if len(words) <= 1:
        return "".join(words)
    return f"{', '.join(words[:-1])} {conjunction} {words[-1]}"


def scope_summary(
    groups: Iterable[ScopeGroup], language: str, threshold: Decimal = Decimal("5")
) -> str:
    """The scope written from the assets (empty without any)."""
    wording = WORDINGS.get((language or "en").lower(), WORDINGS["en"])
    units: dict[tuple[str, str], int] = {}
    for group in groups:
        if group.quantity > 0:
            key = (group.manufacturer.strip(), group.asset_class.strip())
            units[key] = units.get(key, 0) + group.quantity
    total = sum(units.values())
    if not total:
        return ""
    # Negligible groups are left out; the rest from the largest
    kept = sorted(
        ((key, n) for key, n in units.items() if Decimal(n) * 100 / total >= threshold),
        key=lambda item: (-item[1], item[0]),
    )
    # Each manufacturer with its classes (largest first), then manufacturers with the same
    # classes together
    by_manufacturer: dict[str, list[str]] = {}
    manufacturer_units: dict[str, int] = {}
    for (manufacturer, asset_class), n in kept:
        by_manufacturer.setdefault(manufacturer, []).append(asset_class)
        manufacturer_units[manufacturer] = manufacturer_units.get(manufacturer, 0) + n
    parts: dict[tuple[str, ...], list[str]] = {}
    part_units: dict[tuple[str, ...], int] = {}
    for manufacturer, classes in by_manufacturer.items():
        key = tuple(classes)
        parts.setdefault(key, []).append(manufacturer)
        part_units[key] = part_units.get(key, 0) + manufacturer_units[manufacturer]
    ordered = sorted(parts.items(), key=lambda item: -part_units[item[0]])

    def write(classes: tuple[str, ...], manufacturers: list[str]) -> str:
        names = join(manufacturers, wording.conjunction)
        kinds = join(list(classes), wording.conjunction)
        return f"{names} {kinds}" if wording.manufacturer_first else f"{kinds} {names}"

    texts = [write(classes, manufacturers) for classes, manufacturers in ordered[:MAX_PARTS]]
    if len(ordered) > MAX_PARTS:
        texts.append(wording.others)
    return join(texts, wording.conjunction)
