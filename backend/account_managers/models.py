"""Account managers are users with the "Account Manager" role (users app). This app only keeps
its migrations (the former AccountManager table and how it became users)."""

import posixpath
import uuid


def _photo_path(instance, filename: str) -> str:
    """Kept for the migrations' history (0003_photo refers to it)."""
    return f"account-managers/{uuid.uuid4().hex}{posixpath.splitext(filename)[1].lower()}"
