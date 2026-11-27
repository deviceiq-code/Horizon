"""Environments (config/environments.py): Live and Development over different databases.

In tests the Development alias mirrors the test database (settings: TEST MIRROR), so these
check the switching itself — which connection, files folder and session a request uses.
"""

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import connection
from rest_framework.test import APIClient

from config import environments
from inventory.models import Alert
from users.models import Role, UserProfile

needs_development = pytest.mark.skipif(
    "development" not in settings.HORIZON_DATABASES,
    reason="DATABASE_URL_DEVELOPMENT is not configured",
)


def test_unknown_or_missing_cookie_is_the_process_environment(settings):
    settings.HORIZON_DATABASES = {"live": {}, "development": {}}
    settings.HORIZON_ENVIRONMENT = "live"
    assert environments.chosen(None) == "live"
    assert environments.chosen("production") == "live"
    assert environments.chosen("development") == "development"
    assert environments.available() == ["live", "development"]


def test_without_development_only_live_is_offered(settings):
    settings.HORIZON_DATABASES = {"live": {}}
    settings.HORIZON_ENVIRONMENT = "live"
    assert environments.available() == ["live"]
    assert environments.chosen("development") == "live"
    with pytest.raises(ValueError):
        with environments.activate("development"):
            pass


@needs_development
def test_activate_swaps_the_default_connection_and_the_files_folder(settings, tmp_path):
    settings.HORIZON_MEDIA_ROOTS = {**settings.HORIZON_MEDIA_ROOTS, "development": tmp_path}
    own = connection.alias
    assert environments.current() == settings.HORIZON_ENVIRONMENT
    with environments.activate("development"):
        assert connection.alias == "development"
        assert environments.current() == "development"
        assert default_storage.location == str(tmp_path)
    assert connection.alias == own
    assert environments.current() == settings.HORIZON_ENVIRONMENT
    assert default_storage.location == str(settings.MEDIA_ROOT)


@needs_development
def test_the_connection_comes_back_after_an_error():
    with pytest.raises(RuntimeError):
        with environments.activate("development"):
            raise RuntimeError
    assert connection.alias == "default"


@pytest.mark.django_db
def test_login_page_lists_the_environments_without_signing_in():
    response = APIClient().get("/api/auth/environments/")
    assert response.status_code == 200
    assert response.data == {
        "environments": environments.available(),
        "current": settings.HORIZON_ENVIRONMENT,
    }


@needs_development
@pytest.mark.django_db(transaction=True, databases=["default", "development"])
def test_a_request_with_the_cookie_signs_in_and_works_in_development():
    ana = get_user_model().objects.create_user("ana", password="secret-pass-123")
    UserProfile.objects.filter(user=ana).update(environments=["live", "development"])
    client = APIClient()
    client.cookies[environments.COOKIE_NAME] = "development"

    assert client.get("/api/auth/environments/").data["current"] == "development"
    response = client.post(
        "/api/auth/login/", {"username": "ana", "password": "secret-pass-123"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["environment"] == "development"
    assert client.get("/api/auth/me/").data["environment"] == "development"


@pytest.mark.django_db
def test_me_says_which_environment_is_in_use():
    user = get_user_model().objects.create_user("bia", password="secret-pass-123")
    client = APIClient()
    client.force_login(user)
    assert client.get("/api/auth/me/").data["environment"] == settings.HORIZON_ENVIRONMENT


@needs_development
def test_live_can_be_served_for_a_moment_within_development():
    with environments.activate("development"):
        with environments.activate("live"):
            assert connection.alias == "default"
            assert environments.current() == "live"
        assert connection.alias == "development"
        assert environments.current() == "development"
    assert connection.alias == "default"


@needs_development
@pytest.mark.django_db(transaction=True, databases=["default", "development"])
def test_an_environment_not_given_to_the_user_is_refused_and_administrators_warned():
    get_user_model().objects.create_user("bia", password="secret-pass-123")  # Live only
    boss = get_user_model().objects.create_user("boss", password="secret-pass-123")
    Role.administrator().users.add(boss)
    client = APIClient()
    client.cookies[environments.COOKIE_NAME] = "development"
    response = client.post(
        "/api/auth/login/", {"username": "bia", "password": "secret-pass-123"}, format="json"
    )
    assert response.status_code == 403
    assert response.data["code"] == "environment_denied"
    assert "Development (Test)" in response.data["detail"]
    assert client.get("/api/auth/me/").status_code == 403
    alert = Alert.objects.get(kind="environment_denied")
    assert (alert.user, alert.severity, alert.scope) == (boss, "warning", "user")
    assert (alert.params["username"], alert.params["environment"]) == ("bia", "development")
    assert alert.params["address"]
    assert alert.ref.startswith("user:")


@pytest.mark.django_db
def test_administrators_give_each_user_their_environments():
    boss = get_user_model().objects.create_user("boss2", password="secret-pass-123")
    Role.administrator().users.add(boss)
    carla = get_user_model().objects.create_user("carla", password="secret-pass-123")
    client = APIClient()
    client.force_login(boss)
    assert client.get(f"/api/users/{carla.pk}/").data["environments"] == ["live"]
    response = client.patch(
        f"/api/users/{carla.pk}/", {"environments": ["development", "live"]}, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["environments"] == ["live", "development"]
    bad = client.patch(f"/api/users/{carla.pk}/", {"environments": []}, format="json")
    assert bad.status_code == 400
    # Not the environment one is working in, from oneself
    own = client.patch(f"/api/users/{boss.pk}/", {"environments": ["development"]}, format="json")
    assert own.status_code == 400 and "environments" in own.data


@needs_development
def test_each_environments_own_connection_whatever_default_serves():
    from django.db import connections

    live = connections["default"]
    with environments.activate("development"):
        assert environments.connection_of("live") is live
        assert environments.connection_of("development") is connections["development"]
        assert connections["default"] is connections["development"]
