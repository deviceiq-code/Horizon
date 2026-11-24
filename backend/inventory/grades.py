"""Inspection rules (pure, tested): the grade suggested from the test script and the kit
checklist, the recommended destination, and penalty periods that must not overlap (RN-03).

Grade code: conservation (A–D) · functioning (1 works, 2 with restrictions, 3 does not work,
0 not testable) · completeness (C complete, P accessory items missing, I essential parts
missing) — e.g. "B1C".
"""

from datetime import date

PASS, FAIL, NOT_APPLICABLE = "pass", "fail", "na"


def suggest_functioning(test_script: list[str], results: dict[str, str]) -> str:
    """ "1" when every check passed (or does not apply), "2" when any failed; "" while a check
    is unanswered or there is no script (the technician decides — 3 and 0 are theirs)."""
    if not test_script or any(
        results.get(item) not in (PASS, FAIL, NOT_APPLICABLE) for item in test_script
    ):
        return ""
    return "2" if any(results.get(item) == FAIL for item in test_script) else "1"


def suggest_completeness(kit: list[dict], missing: list[str]) -> str:
    """ "C" nothing missing, "P" only accessory items missing, "I" an essential one missing."""
    missing_names = {name.casefold() for name in missing}
    essential = {entry["item"].casefold() for entry in kit if entry.get("essential")}
    if not missing_names:
        return "C"
    return "I" if missing_names & essential else "P"


def recommended_destination(finding_kinds: list[str], functioning: str, irreparable: bool) -> str:
    """An access block → blocked; not working and not worth repairing → scrap; else available."""
    if "access_block" in finding_kinds:
        return "blocked"
    if functioning == "3" and irreparable:
        return "scrap"
    return "available"


def periods_overlap(
    start: date, end: date | None, other_start: date, other_end: date | None
) -> bool:
    """Two validity periods (end None = open) share at least one day."""
    return (end is None or other_start <= end) and (other_end is None or start <= other_end)
