import pytest
from django.contrib.auth import get_user_model

from system.models import DictionaryWord
from users.models import Role

URL = "/api/system/word-dictionary/"


@pytest.fixture
def logged_client(client, db):
    client.force_login(get_user_model().objects.create_user("ana", password="x-Strong-1"))
    return client


@pytest.fixture
def admin_client(client, db):
    user = get_user_model().objects.create_user("bia", password="x-Strong-1")
    Role.administrator().users.add(user)
    client.force_login(user)
    return client


def test_everyone_reads_it_with_the_defaults(logged_client):
    words = {w["replacement"]: w["variants"] for w in logged_client.get(URL).json()}
    assert words["LTDA"] == []
    assert "sa." in words["S/A"]


def test_only_administrators_change_it(logged_client):
    r = logged_client.post(URL, {"replacement": "EIRELI"}, content_type="application/json")
    assert r.status_code == 403


def test_administrators_keep_it(admin_client):
    r = admin_client.post(
        URL,
        {"replacement": "  ME  ", "variants": ["m.e.", "M.E.", "  ", "me"]},
        content_type="application/json",
    )
    assert r.status_code == 201, r.json()
    # Tidied: no blanks, no repeats (any case), not the spelling itself
    assert (r.json()["replacement"], r.json()["variants"]) == ("ME", ["m.e."])
    # A way of typing belongs to one word only
    r = admin_client.post(
        URL, {"replacement": "Ltda.", "variants": ["ltda"]}, content_type="application/json"
    )
    assert r.status_code == 400
    assert "LTDA" in str(r.json())
    r = admin_client.post(URL, {"replacement": "--"}, content_type="application/json")
    assert r.status_code == 400
    word = DictionaryWord.objects.get(replacement="ME")
    assert admin_client.delete(f"{URL}{word.pk}/").status_code == 204
