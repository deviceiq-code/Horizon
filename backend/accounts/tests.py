import pytest
from django.contrib.auth import get_user_model

from .models import UserPreferences


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("tester", password="strong-password-123")


@pytest.fixture
def logged_client(client, user):
    client.force_login(user)
    return client


def _patch(client, data, **extra):
    return client.patch("/api/auth/preferences/", data, content_type="application/json", **extra)


# --- Authentication --------------------------------------------------------------------------


def test_login_and_user_data(client, user):
    r = client.post(
        "/api/auth/login/",
        {"username": "tester", "password": "strong-password-123"},
        content_type="application/json",
    )
    assert r.status_code == 200
    data = client.get("/api/auth/me/").json()
    assert data["username"] == "tester"
    assert data["preferences"]["language"] == "en"
    assert data["preferences"]["theme"] == "system"


def test_login_with_wrong_password(client, user):
    r = client.post(
        "/api/auth/login/",
        {"username": "tester", "password": "wrong"},
        content_type="application/json",
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid username or password."


@pytest.mark.django_db
def test_api_requires_login(client):
    assert client.get("/api/auth/me/").status_code == 403
    assert client.get("/api/auth/preferences/").status_code == 403


# --- Preferences -----------------------------------------------------------------------------


def test_preferences_are_created_with_defaults(logged_client, user):
    assert not UserPreferences.objects.filter(user=user).exists()
    r = logged_client.get("/api/auth/preferences/")
    assert r.status_code == 200
    assert r.json()["language"] == "en"
    assert r.json()["theme"] == "system"
    assert UserPreferences.objects.filter(user=user).count() == 1


def test_updating_preferences_saves_to_database(logged_client, user):
    r = _patch(logged_client, {"language": "pt-br", "theme": "dark"})
    assert r.status_code == 200
    assert r.json()["language"] == "pt-br"
    preferences = UserPreferences.objects.get(user=user)
    assert (preferences.language, preferences.theme) == ("pt-br", "dark")


def test_partial_update_keeps_other_fields(logged_client, user):
    _patch(logged_client, {"theme": "dark"})
    _patch(logged_client, {"language": "es"})
    preferences = UserPreferences.objects.get(user=user)
    assert (preferences.language, preferences.theme) == ("es", "dark")


@pytest.mark.parametrize("data", [{"language": "xx"}, {"theme": "neon"}])
def test_invalid_values_are_rejected(logged_client, user, data):
    assert _patch(logged_client, data).status_code == 400
    preferences = UserPreferences.for_user(user)
    assert (preferences.language, preferences.theme) == ("en", "system")


# --- API response language -------------------------------------------------------------------


def test_anonymous_visitor_gets_messages_in_browser_language(client, user):
    r = client.post(
        "/api/auth/login/",
        {"username": "tester", "password": "wrong"},
        content_type="application/json",
        headers={"accept-language": "pt-br"},
    )
    assert r.json()["detail"] == "Usuário ou senha inválidos."


def test_logged_user_gets_messages_in_preferred_language(logged_client):
    _patch(logged_client, {"language": "es"})
    # Even when the header asks for Portuguese, the saved language (Spanish) wins
    r = _patch(logged_client, {"theme": "neon"}, headers={"accept-language": "pt-br"})
    assert r.status_code == 400
    assert "no es una elección válida" in r.json()["theme"][0]


def test_color_theme_defaults_and_changes(logged_client):
    assert (
        logged_client.get("/api/auth/preferences/").json()["color_theme"] == "metallic_foundations"
    )
    for theme in ("earthy_serene", "sleek_futuristic", "emerald_slate", "metallic_foundations"):
        r = _patch(logged_client, {"color_theme": theme})
        assert (r.status_code, r.json()["color_theme"]) == (200, theme)
    r = _patch(logged_client, {"color_theme": "neon"})
    assert r.status_code == 400
    assert "color_theme" in r.json()


def test_interface_size_defaults_to_automatic(logged_client):
    assert logged_client.get("/api/auth/preferences/").json()["ui_scale"] == "auto"
    for size in ("small", "normal", "large", "auto"):
        r = _patch(logged_client, {"ui_scale": size})
        assert (r.status_code, r.json()["ui_scale"]) == (200, size)
    assert logged_client.get("/api/auth/me/").json()["preferences"]["ui_scale"] == "auto"
    r = _patch(logged_client, {"ui_scale": "huge"})
    assert r.status_code == 400 and "ui_scale" in r.json()


def test_me_has_the_email_and_the_roles_for_display(logged_client, user):
    from users.models import Role

    user.email = "fernando@example.com"
    user.save()
    admin = Role.objects.get(key="administrator")
    admin.users.add(user)
    data = logged_client.get("/api/auth/me/").json()
    assert data["email"] == "fernando@example.com"
    assert data["role_refs"] == [{"name": admin.name, "key": "administrator", "is_system": True}]


def test_date_and_time_formats_default_to_automatic(logged_client):
    data = logged_client.get("/api/auth/preferences/").json()
    assert (data["date_format"], data["time_format"]) == ("auto", "auto")
    r = _patch(logged_client, {"date_format": "ymd", "time_format": "12h"})
    assert (r.status_code, r.json()["date_format"], r.json()["time_format"]) == (200, "ymd", "12h")
    assert logged_client.get("/api/auth/me/").json()["preferences"]["date_format"] == "ymd"
    r = _patch(logged_client, {"date_format": "dd.mm"})
    assert r.status_code == 400 and "date_format" in r.json()


def test_select_on_focus_is_on_by_default(logged_client):
    assert logged_client.get("/api/auth/preferences/").json()["select_on_focus"] is True
    r = _patch(logged_client, {"select_on_focus": False})
    assert (r.status_code, r.json()["select_on_focus"]) == (200, False)
    assert logged_client.get("/api/auth/me/").json()["preferences"]["select_on_focus"] is False


def test_automatic_scope_on_by_default_with_a_5_percent_threshold(logged_client):
    data = logged_client.get("/api/auth/preferences/").json()
    assert (data["auto_scope"], data["scope_threshold"]) == (True, "5.00")
    r = _patch(logged_client, {"auto_scope": False, "scope_threshold": "12.5"})
    assert (r.json()["auto_scope"], r.json()["scope_threshold"]) == (False, "12.50")
    r = _patch(logged_client, {"scope_threshold": "150"})
    assert r.status_code == 400 and "scope_threshold" in r.json()
