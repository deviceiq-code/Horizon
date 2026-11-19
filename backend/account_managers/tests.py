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
    assert set(data["results"][0]) == {"id", "full_name", "email", "created_at", "updated_at"}


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
