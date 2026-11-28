import pytest
from django.contrib.auth import get_user_model

from .models import ServiceKind, ServiceProvider

URL = "/api/service-providers/"
CNPJ = "11222333000181"
CNPJ_ALPHANUMERIC = "12ABC34501DE35"


@pytest.fixture
def logged_client(client, db):
    user = get_user_model().objects.create_user("tester", password="strong-password-123")
    client.force_login(user)
    return client


@pytest.fixture
def storage(db):
    return ServiceProvider.objects.create(
        name="Armazéns Gerais Ltda", trade_name="ArmaGerais", tax_id=CNPJ,
        services=[ServiceKind.WAREHOUSING, ServiceKind.TRANSPORT], city="Barueri", state="SP",
    )  # fmt: skip


@pytest.fixture
def refurbisher(db):
    return ServiceProvider.objects.create(
        name="Recondiciona S.A.", tax_id=CNPJ_ALPHANUMERIC, services=[ServiceKind.REFURBISHMENT],
        is_active=False,
    )  # fmt: skip


def _post(client, data):
    return client.post(URL, data, content_type="application/json")


def _patch(client, provider, data):
    return client.patch(f"{URL}{provider.id}/", data, content_type="application/json")


def test_requires_login(client, db):
    assert client.get(URL).status_code == 403


def test_read_only_here(logged_client, storage):
    """Service providers are a role of business entities: written at /api/business-entities/."""
    assert _post(logged_client, {"name": "X", "tax_id": CNPJ}).status_code == 405
    assert logged_client.delete(f"{URL}{storage.id}/").status_code == 405


def test_list_filters_and_search(logged_client, storage, refurbisher):
    names = lambda r: [p["name"] for p in r.json()["results"]]  # noqa: E731
    assert names(logged_client.get(URL)) == ["Armazéns Gerais Ltda", "Recondiciona S.A."]
    assert names(logged_client.get(URL, {"service": "warehousing"})) == ["Armazéns Gerais Ltda"]
    assert names(logged_client.get(URL, {"is_active": "false"})) == ["Recondiciona S.A."]
    assert names(logged_client.get(URL, {"search": "armagerais"})) == ["Armazéns Gerais Ltda"]
    # Tax ID with punctuation
    assert names(logged_client.get(URL, {"search": "11.222.333"})) == ["Armazéns Gerais Ltda"]


def test_column_filters(logged_client, storage, refurbisher):
    storage.entity.keywords = ["galpão seco"]
    storage.entity.save()
    names = lambda params: [p["name"] for p in logged_client.get(URL, params).json()["results"]]  # noqa: E731
    assert names({"name": "armagerais"}) == ["Armazéns Gerais Ltda"]  # trade name
    assert names({"name": "galpão"}) == ["Armazéns Gerais Ltda"]  # keyword
    assert names({"tax_id": "12.abc"}) == ["Recondiciona S.A."]
    assert names({"location": "barueri"}) == ["Armazéns Gerais Ltda"]
    assert names({"location": "sp"}) == ["Armazéns Gerais Ltda"]
