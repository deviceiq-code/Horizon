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
    get_user_model().objects.create_user("ana", password="secret-pass-123")
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
