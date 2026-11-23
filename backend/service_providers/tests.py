import pytest
from django.contrib.auth import get_user_model

from inventory.models import Warehouse

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


def test_create_normalizes_fields(logged_client):
    response = _post(
        logged_client,
        {
            "name": "  Logística   Rápida Ltda ",
            "tax_id": "11.222.333/0001-81",
            "services": ["transport", "warehousing", "transport"],
            "contact_name": " Ana   Souza ",
            "email": " Contato@Exemplo.COM ",
            "postal_code": "06460-000",
            "state": "sp",
            "keywords": ["Galpão", "galpão"],
        },
    )
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["name"] == "Logística Rápida Ltda"
    assert data["tax_id"] == CNPJ
    # Kept in the choices' order, without repeats
    assert data["services"] == ["warehousing", "transport"]
    assert data["contact_name"] == "Ana Souza"
    assert data["email"] == "contato@exemplo.com"
    assert data["postal_code"] == "06460000"
    assert data["state"] == "SP"
    assert data["keywords"] == ["galpão"]
    assert data["warehouses_count"] == 0


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"services": []}, "services"),
        ({"services": ["catering"]}, "services"),
        ({"tax_id": "11222333000100"}, "tax_id"),
        ({"postal_code": "123"}, "postal_code"),
        ({"state": "XX"}, "state"),
        ({"name": "   "}, "name"),
    ],
)
def test_create_rejects_invalid_fields(logged_client, data, field):
    payload = {"name": "Prestador", "tax_id": CNPJ, "services": ["transport"], **data}
    response = _post(logged_client, payload)
    assert response.status_code == 400
    assert field in response.json()


def test_tax_id_is_unique_per_country(logged_client, storage):
    response = _post(logged_client, {"name": "Outro", "tax_id": CNPJ, "services": ["repair"]})
    assert response.status_code == 400
    assert "tax_id" in response.json()
    # Abroad tax IDs are free-form and not CPF/CNPJ-checked
    response = _post(
        logged_client,
        {"name": "Other", "tax_id": CNPJ, "country": "us", "services": ["repair"]},
    )
    assert response.status_code == 201, response.json()


def test_list_filters_and_search(logged_client, storage, refurbisher):
    names = lambda r: [p["name"] for p in r.json()["results"]]  # noqa: E731
    assert names(logged_client.get(URL)) == ["Armazéns Gerais Ltda", "Recondiciona S.A."]
    assert names(logged_client.get(URL, {"service": "warehousing"})) == ["Armazéns Gerais Ltda"]
    assert names(logged_client.get(URL, {"is_active": "false"})) == ["Recondiciona S.A."]
    assert names(logged_client.get(URL, {"search": "armagerais"})) == ["Armazéns Gerais Ltda"]
    # Tax ID with punctuation
    assert names(logged_client.get(URL, {"search": "11.222.333"})) == ["Armazéns Gerais Ltda"]


def test_running_warehouses_blocks_delete_and_removing_warehousing(logged_client, storage):
    Warehouse.objects.create(name="CD Barueri", ownership="outsourced", service_provider=storage)
    assert logged_client.get(f"{URL}{storage.id}/").json()["warehouses_count"] == 1

    response = logged_client.delete(f"{URL}{storage.id}/")
    assert response.status_code == 409
    assert response.json()["detail"]

    response = _patch(logged_client, storage, {"services": ["transport"]})
    assert response.status_code == 400
    assert "services" in response.json()
    # Other changes keep working
    assert _patch(logged_client, storage, {"services": ["warehousing"]}).status_code == 200


def test_delete_unused(logged_client, refurbisher):
    assert logged_client.delete(f"{URL}{refurbisher.id}/").status_code == 204
    assert not ServiceProvider.objects.exists()


def test_column_filters(logged_client, storage, refurbisher):
    storage.keywords = ["galpão seco"]
    storage.save()
    names = lambda params: [p["name"] for p in logged_client.get(URL, params).json()["results"]]  # noqa: E731
    assert names({"name": "armagerais"}) == ["Armazéns Gerais Ltda"]  # trade name
    assert names({"name": "galpão"}) == ["Armazéns Gerais Ltda"]  # keyword
    assert names({"tax_id": "12.abc"}) == ["Recondiciona S.A."]
    assert names({"location": "barueri"}) == ["Armazéns Gerais Ltda"]
    assert names({"location": "sp"}) == ["Armazéns Gerais Ltda"]
