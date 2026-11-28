from datetime import datetime, timedelta

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from catalogs.models import Manufacturer
from entities.models import BusinessEntity
from users.models import Role

from .journal import period_start
from .models import Release
from .releases import current_version, release_notes

URL = "/api/system/journal/"


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("reader", password="x")


@pytest.fixture
def client_for(client):
    def login(user):
        client.force_login(user)
        return client

    return login


def _events(response):
    return {e["key"]: e["count"] for e in response.json()["events"]}


def test_period_start():
    now = timezone.make_aware(datetime(2026, 11, 28, 15, 30))
    assert period_start(1, now) == timezone.make_aware(datetime(2026, 11, 28, 0, 0))
    assert period_start(7, now) == now - timedelta(days=7)


def test_counts_only_of_what_happened_in_the_period(user, client_for):
    client = client_for(user)
    BusinessEntity.objects.create(name="Nova", tax_id="A1")
    old = BusinessEntity.objects.create(name="Antiga", tax_id="A2")
    BusinessEntity.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))
    Manufacturer.objects.create(name="Dell")
    body = client.get(URL).json()
    assert body["days"] == 7  # the default
    counts = _events(client.get(URL))
    assert counts["business_entities.created"] == 1
    assert counts["manufacturers.created"] == 1
    assert "efmv_analyses.created" not in counts  # nothing happened: left out
    assert _events(client.get(URL, {"days": "30"}))["business_entities.created"] == 2
    # Never names nor values: only keys and counts
    assert all(set(e) == {"key", "count"} for e in body["events"])


def test_only_modules_the_user_may_open(user, client_for):
    get_user_model().objects.create_user("someone")
    assert "users.created" not in _events(client_for(user).get(URL))
    admin = get_user_model().objects.create_user("boss", password="x")
    Role.administrator().users.add(admin)
    assert _events(client_for(admin).get(URL))["users.created"] >= 2


def test_both_parts_shown_by_default(user, client_for):
    data = client_for(user).get("/api/auth/preferences/").json()
    assert (data["show_data_journal"], data["show_system_journal"]) == (True, True)
    assert data["journal_layout"] == "vertical"
    client = client_for(user)
    r = client.patch(
        "/api/auth/preferences/", {"journal_layout": "diagonal"}, content_type="application/json"
    )
    assert r.status_code == 400


def test_the_period_is_the_users_preference(user, client_for):
    client = client_for(user)
    client.patch("/api/auth/preferences/", {"journal_days": 30}, content_type="application/json")
    assert client.get(URL).json()["days"] == 30
    r = client.patch("/api/auth/preferences/", {"journal_days": 5}, content_type="application/json")
    assert r.status_code == 400


def test_releases_newest_first_in_the_users_language(user, client_for, db):
    Release.objects.create(
        version="1.0.10", released_on="2026-12-10", notes={"en": ["Ten"], "pt-br": ["Dez"]}
    )
    Release.objects.create(version="1.0.9", released_on="2026-12-09", notes={"en": ["Nine"]})
    assert current_version() == "1.0.10"  # by number, not as text
    assert [r["version"] for r in release_notes("en")][:2] == ["1.0.10", "1.0.9"]
    assert release_notes("pt-br")[0]["notes"] == ["Dez"]
    assert release_notes("es")[1]["notes"] == ["Nine"]  # English when missing
    client = client_for(user)
    client.patch("/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json")
    body = client.get(URL).json()
    assert body["version"] == "1.0.10"
    assert body["releases"][0]["notes"] == ["Dez"]


@pytest.mark.django_db
def test_every_release_has_its_notes_in_every_language():
    """Release notes are always written in all the system's languages, as many in each."""
    languages = [code for code, _ in settings.LANGUAGES]
    releases = list(Release.objects.all())
    assert releases, "the migrations add the releases"
    for release in releases:
        counts = {language: len(release.notes.get(language) or []) for language in languages}
        assert all(counts.values()), (release.version, counts)
        assert len(set(counts.values())) == 1, (release.version, counts)


def test_the_latest_releases_or_the_whole_history(user, client_for, db):
    for n in range(10, 17):
        Release.objects.create(version=f"1.1.{n}", released_on="2026-12-01", notes={"en": ["x"]})
    client = client_for(user)
    body = client.get(URL).json()
    assert len(body["releases"]) == 5 and body["releases_total"] > 5
    assert len(client.get(URL, {"releases": "all"}).json()["releases"]) == body["releases_total"]
