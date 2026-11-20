import pytest

from pricing.models import PricingSettings
from users.models import Role

URL = "/api/pricing/settings/"


@pytest.fixture
def admin_client(client, user):
    Role.administrator().users.add(user)
    client.force_login(user)
    return client


def test_everyone_signed_in_reads_the_defaults(logged_client):
    data = logged_client.get(URL).json()
    assert data["compatible_percent"] == "5.00"
    assert (data["below_percent"], data["above_percent"]) == ("10.00", "10.00")
    assert (data["validity_months"], data["accept_expired"]) == (12, True)


def test_only_administrators_change_it(logged_client):
    r = logged_client.patch(URL, {"below_percent": "8"}, content_type="application/json")
    assert r.status_code == 403


def test_administrator_changes_it(admin_client):
    r = admin_client.patch(
        URL,
        {"compatible_percent": "3", "above_percent": "7.5", "validity_months": 6,
         "accept_expired": False},
        content_type="application/json",
    )  # fmt: skip
    assert r.status_code == 200, r.json()
    assert r.json()["above_percent"] == "7.50"
    assert r.json()["updated_by_name"] == "Ana Souza"
    settings = PricingSettings.current()
    assert (settings.validity_months, settings.accept_expired) == (6, False)


def test_limits_must_be_beyond_the_compatible_range(admin_client):
    r = admin_client.patch(
        URL, {"compatible_percent": "10", "below_percent": "10"}, content_type="application/json"
    )
    assert r.status_code == 400
    assert set(r.json()) == {"below_percent", "above_percent"}
    r = admin_client.patch(URL, {"validity_months": 0}, content_type="application/json")
    assert r.status_code == 400
