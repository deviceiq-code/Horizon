"""Names of asset classes in each language: English (the name and its plural, required) and
optional translations ({"pt-br": {"name": ..., "plural": ...}, "es": {...}}); an empty
translation falls back to English. Pure functions, tested."""

from collections.abc import Mapping

ENGLISH = "en"


def english_plural(name: str) -> str:
    """A plural for an English name, by the usual rules on its last word ("3D Printer" →
    "3D Printers", "Battery" → "Batteries", "Switch" → "Switches"). Words already ending in "s"
    are kept ("Accessories"). A suggestion: the plural can be corrected in the catalog."""
    name = name.strip()
    if not name:
        return name
    head, _, last = name.rpartition(" ")
    lower = last.lower()
    if lower.endswith("s"):
        plural = last
    elif lower.endswith("y") and len(last) > 1 and lower[-2] not in "aeiou":
        plural = last[:-1] + "ies"
    elif lower.endswith(("x", "z", "ch", "sh")):
        plural = last + "es"
    else:
        plural = last + "s"
    return f"{head} {plural}" if head else plural


def localized(
    name: str, plural: str, translations: Mapping | None, language: str, *, many: bool
) -> str:
    """The name (or plural, `many`) in `language`; English when not translated."""
    key = "plural" if many else "name"
    english = plural if many else name
    if language and language.lower() != ENGLISH:
        entry = (translations or {}).get(language.lower()) or {}
        text = (entry.get(key) or "").strip()
        if text:
            return text
    return english
