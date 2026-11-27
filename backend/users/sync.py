"""Users are one and the same in every environment: Live keeps them, the others a copy.

The other environments' records point to users (created_by, account managers…) inside their
own database, so each keeps a copy of Live's users with the same ids: roles, users, who has
which role, profiles (photo and verticals included) and preferences. Users are only changed in
Live (users/views.py and the preferences write there) and copied right after, and before
signing in to another environment (accounts/views.py) — so they never differ for long.
"""

import shutil
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.color import no_style
from django.db import connection, transaction
from django.db.models import ProtectedError

from accounts.models import UserPreferences
from config import environments
from config.environments import LIVE

from .models import Role, UserProfile


def _fields(model, *skip: str) -> list[str]:
    return [f.attname for f in model._meta.concrete_fields if f.attname not in skip]


def _copies() -> list[str]:
    """The environments that keep a copy: the others than Live, on a database of their own (in
    tests they share the test database — nothing to copy)."""
    # Their own connections: "default" may be serving another environment right now
    live_name = environments.connection_of(LIVE).settings_dict["NAME"]
    return [
        name
        for name in environments.available()
        if name != LIVE and environments.connection_of(name).settings_dict["NAME"] != live_name
    ]


def _read_live() -> dict:
    User = get_user_model()
    with environments.activate(LIVE):
        return {
            "roles": list(Role.objects.values(*_fields(Role))),
            "users": list(User.objects.values(*_fields(User))),
            "memberships": list(Role.users.through.objects.values_list("role_id", "user_id")),
            "profiles": list(UserProfile.objects.values(*_fields(UserProfile, "id"))),
            "verticals": list(
                UserProfile.verticals.through.objects.values_list(
                    "userprofile__user_id", "vertical_id"
                )
            ),
            "preferences": list(UserPreferences.objects.values(*_fields(UserPreferences, "id"))),
        }


def _upsert(model, rows: list[dict], key: str) -> None:
    """Rows by `key` ("id": the same ids as Live; "user_id": one per user): changed in place,
    missing ones created (no signals: the copy is exactly Live's)."""
    existing = set(model.objects.values_list(key, flat=True))
    new = []
    for row in rows:
        if row[key] in existing:
            values = {k: v for k, v in row.items() if k != key}
            model.objects.filter(**{key: row[key]}).update(**values)
        else:
            new.append(model(**row))
    model.objects.bulk_create(new)


def _copy_photos(profiles: list[dict], name: str) -> None:
    """Photos are files: the copy's folder gets the ones it lacks."""
    source = Path(environments.media_root(LIVE))
    target = Path(environments.media_root(name))
    for profile in profiles:
        photo = profile.get("photo")
        if photo and (source / photo).exists() and not (target / photo).exists():
            (target / photo).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / photo, target / photo)


def _write(name: str, data: dict) -> None:
    User = get_user_model()
    with environments.activate(name), transaction.atomic():
        _upsert(Role, data["roles"], "id")
        _upsert(User, data["users"], "id")
        user_ids = {row["id"] for row in data["users"]}
        # Gone from Live: gone here too — or only inactive when records point to them
        for user in User.objects.exclude(pk__in=user_ids):
            try:
                with transaction.atomic():
                    user.delete()
            except ProtectedError:
                User.objects.filter(pk=user.pk).update(is_active=False)
        Role.objects.exclude(pk__in={row["id"] for row in data["roles"]}).delete()

        Through = Role.users.through
        Through.objects.all().delete()
        Through.objects.bulk_create(Through(role_id=r, user_id=u) for r, u in data["memberships"])

        _upsert(UserProfile, data["profiles"], "user_id")
        _upsert(UserPreferences, data["preferences"], "user_id")
        # Verticals are this environment's records: only those that exist here
        here = set(UserProfile.verticals.field.related_model.objects.values_list("pk", flat=True))
        profile_of = dict(UserProfile.objects.values_list("user_id", "pk"))
        Verticals = UserProfile.verticals.through
        Verticals.objects.all().delete()
        Verticals.objects.bulk_create(
            Verticals(userprofile_id=profile_of[u], vertical_id=v)
            for u, v in data["verticals"]
            if v in here and u in profile_of
        )
        # Ids came from Live: the sequences go past them
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(no_style(), [User, Role]):
                cursor.execute(sql)
    _copy_photos(data["profiles"], name)


def sync_users() -> list[str]:
    """Copy Live's users to every other environment; returns where they were copied."""
    targets = _copies()
    if targets:
        data = _read_live()
        for name in targets:
            _write(name, data)
    return targets


def sync_preferences(user_id: int) -> None:
    """One user's preferences changed in Live (saved often: menus, grids…): only they are
    copied to the other environments."""
    targets = _copies()
    if not targets:
        return
    with environments.activate(LIVE):
        rows = list(
            UserPreferences.objects.filter(user_id=user_id).values(*_fields(UserPreferences, "id"))
        )
    for name in targets:
        with environments.activate(name):
            _upsert(UserPreferences, rows, "user_id")
