import pytest
from django.contrib.auth import get_user_model

from .models import AccountManager

URL = "/api/account-managers/"


@pytest.fixture
def logged_client(client, db):
    user = get_user_model().objects.create_user("tester", password="strong-password-123")
    client.force_login(user)
    return client


@pytest.fixture
def managers(db):
    return [
        AccountManager.objects.create(full_name="Carla Mendes", email="carla@example.com"),
        AccountManager.objects.create(full_name="Ana Souza", email="ana@example.com"),
        AccountManager.objects.create(full_name="Bruno Lima", email="bruno@corp.com"),
    ]


def _post(client, data, **extra):
    return client.post(URL, data, content_type="application/json", **extra)


def _patch(client, pk, data):
    return client.patch(f"{URL}{pk}/", data, content_type="application/json")


@pytest.mark.django_db
def test_requires_login(client):
    assert client.get(URL).status_code == 403
    assert _post(client, {"full_name": "X", "email": "x@example.com"}).status_code == 403


# --- List / search / ordering / pagination ---------------------------------------------------


def test_list_is_paginated_and_ordered_by_name(logged_client, managers):
    data = logged_client.get(URL).json()
    assert data["count"] == 3
    assert [m["full_name"] for m in data["results"]] == ["Ana Souza", "Bruno Lima", "Carla Mendes"]
    assert set(data["results"][0]) == {
        "id",
        "full_name",
        "email",
        "verticals",
        "verticals_detail",
        "created_at",
        "updated_at",
    }


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("souza", ["Ana Souza"]),
        ("CORP.COM", ["Bruno Lima"]),
        ("example", ["Ana Souza", "Carla Mendes"]),
    ],
)
def test_search_by_name_or_email(logged_client, managers, term, expected):
    results = logged_client.get(URL, {"search": term}).json()["results"]
    assert [m["full_name"] for m in results] == expected


def test_ordering(logged_client, managers):
    results = logged_client.get(URL, {"ordering": "-email"}).json()["results"]
    assert [m["email"] for m in results] == [
        "carla@example.com",
        "bruno@corp.com",
        "ana@example.com",
    ]


def test_page_size(logged_client, managers):
    data = logged_client.get(URL, {"page_size": 2, "page": 2}).json()
    assert data["count"] == 3
    assert [m["full_name"] for m in data["results"]] == ["Carla Mendes"]


# --- Create / update / delete ----------------------------------------------------------------


def test_create_normalizes_name_and_email(logged_client):
    r = _post(logged_client, {"full_name": "  Diego   Alves ", "email": " Diego@Example.COM "})
    assert r.status_code == 201
    manager = AccountManager.objects.get(pk=r.json()["id"])
    assert (manager.full_name, manager.email) == ("Diego Alves", "diego@example.com")


@pytest.mark.parametrize(
    "data",
    [
        {"full_name": "", "email": "a@example.com"},
        {"full_name": "   ", "email": "a@example.com"},
        {"full_name": "Someone", "email": "not-an-email"},
        {"full_name": "Someone"},
        {"email": "a@example.com"},
    ],
)
def test_create_validates_fields(logged_client, data):
    assert _post(logged_client, data).status_code == 400
    assert AccountManager.objects.count() == 0


def test_email_must_be_unique_ignoring_case(logged_client, managers):
    r = _post(logged_client, {"full_name": "Other Ana", "email": "ANA@example.com"})
    assert r.status_code == 400
    assert r.json()["email"] == ["An account manager with this email already exists."]


def test_update(logged_client, managers):
    ana = managers[1]
    r = _patch(logged_client, ana.pk, {"full_name": "Ana Souza Costa"})
    assert r.status_code == 200
    ana.refresh_from_db()
    assert (ana.full_name, ana.email) == ("Ana Souza Costa", "ana@example.com")


def test_update_keeping_own_email_is_allowed(logged_client, managers):
    ana = managers[1]
    assert _patch(logged_client, ana.pk, {"email": "ANA@example.com"}).status_code == 200


def test_update_to_another_managers_email_is_rejected(logged_client, managers):
    ana = managers[1]
    assert _patch(logged_client, ana.pk, {"email": "bruno@corp.com"}).status_code == 400


def test_delete(logged_client, managers):
    ana = managers[1]
    assert logged_client.delete(f"{URL}{ana.pk}/").status_code == 204
    assert not AccountManager.objects.filter(pk=ana.pk).exists()


def test_validation_messages_follow_user_language(logged_client, managers):
    logged_client.patch(
        "/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json"
    )
    r = _post(logged_client, {"full_name": "Other Ana", "email": "ana@example.com"})
    assert r.json()["email"] == ["Já existe um account manager com este e-mail."]


# --- Business verticals the account manager works in ----------------------------------------


@pytest.fixture
def verticals(db):
    from catalogs.models import SubVertical, Vertical

    def make(name, **fields):
        vertical = Vertical.objects.create(name=name, **fields)
        SubVertical.objects.create(vertical=vertical, **SubVertical.general_defaults())
        return vertical

    return {
        "industry": make("Industry"),
        "it": make("IT"),
        "agro": make("Agribusiness", is_enabled=False),
    }


def test_create_with_verticals(logged_client, verticals):
    r = _post(
        logged_client,
        {
            "full_name": "Diego Alves",
            "email": "diego@example.com",
            "verticals": [verticals["it"].pk, verticals["industry"].pk],
        },
    )
    assert r.status_code == 201, r.json()
    manager = AccountManager.objects.get(pk=r.json()["id"])
    assert set(manager.verticals.all()) == {verticals["it"], verticals["industry"]}
    # Detail sorted by name, with the enabled flag
    assert r.json()["verticals_detail"] == [
        {"id": verticals["industry"].pk, "name": "Industry", "is_enabled": True},
        {"id": verticals["it"].pk, "name": "IT", "is_enabled": True},
    ]


def test_create_without_verticals(logged_client, db):
    r = _post(logged_client, {"full_name": "Diego Alves", "email": "diego@example.com"})
    assert r.status_code == 201
    assert r.json()["verticals"] == []


def test_update_replaces_verticals(logged_client, managers, verticals):
    ana = managers[1]
    ana.verticals.set([verticals["industry"], verticals["it"]])
    r = _patch(logged_client, ana.pk, {"verticals": [verticals["agro"].pk]})
    assert r.status_code == 200
    assert list(ana.verticals.all()) == [verticals["agro"]]


def test_update_without_verticals_keeps_them(logged_client, managers, verticals):
    ana = managers[1]
    ana.verticals.set([verticals["industry"]])
    assert _patch(logged_client, ana.pk, {"full_name": "Ana S."}).status_code == 200
    assert list(ana.verticals.all()) == [verticals["industry"]]


def test_unknown_vertical_is_rejected(logged_client, db):
    r = _post(
        logged_client,
        {"full_name": "Diego Alves", "email": "diego@example.com", "verticals": [999999]},
    )
    assert r.status_code == 400
    assert "verticals" in r.json()


def test_search_by_vertical_name(logged_client, managers, verticals):
    managers[1].verticals.set([verticals["industry"]])
    managers[2].verticals.set([verticals["industry"], verticals["it"]])
    results = logged_client.get(URL, {"search": "industry"}).json()["results"]
    assert [m["full_name"] for m in results] == ["Ana Souza", "Bruno Lima"]  # each once


def test_vertical_shows_its_account_managers(logged_client, managers, verticals):
    managers[0].verticals.set([verticals["it"]])
    managers[1].verticals.set([verticals["it"]])
    r = logged_client.get(f"/api/catalogs/verticals/{verticals['it'].pk}/")
    assert [m["full_name"] for m in r.json()["account_managers_detail"]] == [
        "Ana Souza",
        "Carla Mendes",
    ]


def test_deleting_a_vertical_removes_it_from_account_managers(logged_client, managers, verticals):
    managers[1].verticals.set([verticals["industry"], verticals["it"]])
    r = logged_client.delete(f"/api/catalogs/verticals/{verticals['industry'].pk}/")
    assert r.status_code == 204
    assert list(managers[1].verticals.all()) == [verticals["it"]]
