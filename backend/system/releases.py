"""Horizon's versions and what each one brought (`system.models.Release`; shown to everyone in
the Home's journal).

Each change delivered adds a release — a data migration in `system/migrations/`, so Live and
Development get the same — raising only the last number (1.0.0 → 1.0.1); the others change
only when Fernando says so. Notes are written for the users — what they can now do —, in every
language (en, pt-br, es), never the list of commits.
"""

from .models import Release


def releases() -> list[Release]:
    """Newest first, by version number."""
    return sorted(Release.objects.all(), key=lambda release: release.number, reverse=True)


def current_version() -> str:
    newest = releases()
    return newest[0].version if newest else ""


def release_notes(language: str, limit: int | None = None) -> list[dict]:
    """The releases, newest first, with their notes in the language (English when missing)."""
    rows = [
        {
            "version": release.version,
            "date": release.released_on.isoformat(),
            "notes": release.notes.get(language) or release.notes.get("en") or [],
        }
        for release in releases()
    ]
    return rows[:limit] if limit else rows
