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
    assert data["preferences"]["theme"] == "light"


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
    assert r.json()["theme"] == "light"
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
    assert (preferences.language, preferences.theme) == ("en", "light")


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
    assert logged_client.get("/api/auth/preferences/").json()["color_theme"] == "emerald_slate"
    for theme in ("metallic_foundations", "earthy_serene", "sleek_futuristic", "emerald_slate"):
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


def test_number_format_currency_and_interface_state(logged_client, user):
    r = logged_client.get("/api/auth/preferences/").json()
    assert (r["number_format"], r["currency"], r["currency_display"], r["ui_state"]) == (
        "auto",
        "BRL",
        "symbol",
        {},
    )
    assert _patch(logged_client, {"currency": "USD"}).json()["currency"] == "USD"
    assert _patch(logged_client, {"currency": "XYZ"}).status_code == 400
    assert _patch(logged_client, {"currency_display": "none"}).status_code == 400
    assert (r["web_search"], r["web_search_engine"]) == (True, "google")
    assert _patch(logged_client, {"web_search": False}).json()["web_search"] is False
    assert (
        _patch(logged_client, {"web_search_engine": "duckduckgo"}).json()["web_search_engine"]
        == "duckduckgo"
    )
    assert _patch(logged_client, {"web_search_engine": "altavista"}).status_code == 400
    assert _patch(logged_client, {"percent_places": 4}).json()["percent_places"] == 4
    for places in (0, 6):
        assert _patch(logged_client, {"percent_places": places}).status_code == 400
    state = {"sideMenu": {"wide": "closed"}, "filters": {"customers": True}}
    r = _patch(
        logged_client,
        {"number_format": "space_comma", "currency_display": "code", "ui_state": state},
    )
    assert r.status_code == 200, r.json()
    prefs = UserPreferences.objects.get(user=user)
    assert (prefs.number_format, prefs.currency_display, prefs.ui_state) == (
        "space_comma",
        "code",
        state,
    )
    assert _patch(logged_client, {"number_format": "x"}).status_code == 400
    assert _patch(logged_client, {"ui_state": ["not", "an", "object"]}).status_code == 400
    assert _patch(logged_client, {"ui_state": {"big": "x" * 30_000}}).status_code == 400


@pytest.mark.django_db
def test_every_failed_sign_in_is_told_to_the_administrators():
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from inventory.models import Alert
    from users.models import Role

    User = get_user_model()
    boss = User.objects.create_user("boss", password="Boss-password-2026")
    Role.administrator().users.add(boss)
    dora = User.objects.create_user("dora", password="Dora-password-2026")
    client = APIClient()
    wrong = {"username": "dora", "password": "nope"}
    assert client.post("/api/auth/login/", wrong, format="json").status_code == 400
    alert = Alert.objects.get(kind="login_failed")
    # An error (red), each attempt
    assert (alert.user, alert.severity, alert.ref) == (boss, "error", f"user:{dora.pk}")
    assert (alert.params["username"], alert.params["environment"]) == ("dora", "live")
    assert alert.params["address"] == "127.0.0.1"
    # An unknown user too (nothing to open); each attempt its own
    client.post("/api/auth/login/", {"username": "ghost", "password": "x"}, format="json")
    client.post("/api/auth/login/", wrong, format="json")
    assert Alert.objects.filter(kind="login_failed").count() == 3
    assert Alert.objects.get(kind="login_failed", params__username="ghost").ref == ""
    # Signing in well: nobody warned
    ok = {"username": "dora", "password": "Dora-password-2026"}
    assert client.post("/api/auth/login/", ok, format="json").status_code == 200
    assert Alert.objects.filter(kind="login_failed").count() == 3
