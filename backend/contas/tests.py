import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_login_e_dados_do_usuario(client):
    get_user_model().objects.create_user("teste", password="senha-forte-123")
    r = client.post(
        "/api/auth/login/",
        {"username": "teste", "password": "senha-forte-123"},
        content_type="application/json",
    )
    assert r.status_code == 200
    assert client.get("/api/auth/me/").json()["username"] == "teste"


@pytest.mark.django_db
def test_login_com_senha_errada(client):
    get_user_model().objects.create_user("teste", password="senha-forte-123")
    r = client.post(
        "/api/auth/login/",
        {"username": "teste", "password": "errada"},
        content_type="application/json",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_api_exige_login(client):
    assert client.get("/api/auth/me/").status_code == 403
