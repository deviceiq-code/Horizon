import pytest
from django.contrib.auth import get_user_model

from catalogs.models import Vertical
from service_providers.models import ServiceKind, ServiceProvider

from .models import Warehouse

URL = "/api/inventory/warehouses/"


@pytest.fixture
def logged_client(client, db):
    user = get_user_model().objects.create_user("tester", password="strong-password-123")
    client.force_login(user)
    return client


@pytest.fixture
def it(db):
    return Vertical.objects.create(name="Information Technology")


@pytest.fixture
def health(db):
    return Vertical.objects.create(name="Healthcare")


@pytest.fixture
def storage(db):
    return ServiceProvider.objects.create(
        name="Armazéns Gerais Ltda", trade_name="ArmaGerais", tax_id="11222333000181",
        services=[ServiceKind.WAREHOUSING],
    )  # fmt: skip


@pytest.fixture
def carrier(db):
    return ServiceProvider.objects.create(
        name="Transportes Ltda", tax_id="12ABC34501DE35", services=[ServiceKind.TRANSPORT]
    )


def _post(client, data):
    return client.post(URL, data, content_type="application/json")


def _patch(client, warehouse, data):
    return client.patch(f"{URL}{warehouse.id}/", data, content_type="application/json")


def test_requires_login(client, db):
    assert client.get(URL).status_code == 403


def test_create_own(logged_client, it, health):
    response = _post(
        logged_client,
        {
            "name": "  CD   Campinas ",
            "verticals": [it.id, health.id, it.id],
            "ownership": "own",
            "postal_code": "13010-100",
            "city": "Campinas",
            "state": "sp",
            "keywords": ["Matriz"],
        },
    )
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["name"] == "CD Campinas"
    assert data["service_provider"] is None
    assert data["service_provider_detail"] is None
    assert data["postal_code"] == "13010100"
    assert data["state"] == "SP"
    assert data["keywords"] == ["matriz"]
    assert sorted(data["verticals"]) == sorted([it.id, health.id])
    assert [v["name"] for v in data["verticals_detail"]] == ["Healthcare", "Information Technology"]


def test_create_outsourced(logged_client, storage, it):
    response = _post(
        logged_client,
        {
            "name": "CD Barueri",
            "ownership": "outsourced",
            "service_provider": storage.id,
            "verticals": [it.id],
        },
    )
    assert response.status_code == 201, response.json()
    assert response.json()["service_provider_detail"] == {"id": storage.id, "name": "ArmaGerais"}


def test_outsourced_needs_a_warehousing_provider(logged_client, storage, carrier, it):
    response = _post(logged_client, {"name": "CD", "ownership": "outsourced", "verticals": [it.id]})
    assert response.status_code == 400
    assert "service_provider" in response.json()

    response = _post(
        logged_client,
        {
            "name": "CD",
            "ownership": "outsourced",
            "service_provider": carrier.id,
            "verticals": [it.id],
        },
    )
    assert response.status_code == 400
    assert "service_provider" in response.json()

    storage.is_active = False
    storage.save()
    response = _post(
        logged_client,
        {
            "name": "CD",
            "ownership": "outsourced",
            "service_provider": storage.id,
            "verticals": [it.id],
        },
    )
    assert response.status_code == 400
    assert "service_provider" in response.json()


def test_provider_deactivated_later_does_not_block_editing(logged_client, storage):
    warehouse = Warehouse.objects.create(
        name="CD Barueri", ownership="outsourced", service_provider=storage
    )
    storage.is_active = False
    storage.save()
    response = _patch(
        logged_client, warehouse, {"service_provider": storage.id, "notes": "Contrato até 2027"}
    )
    assert response.status_code == 200, response.json()


def test_own_drops_the_provider(logged_client, storage):
    warehouse = Warehouse.objects.create(
        name="CD Barueri", ownership="outsourced", service_provider=storage
    )
    response = _patch(logged_client, warehouse, {"ownership": "own"})
    assert response.status_code == 200, response.json()
    warehouse.refresh_from_db()
    assert warehouse.service_provider is None


def test_name_is_unique_case_insensitive(logged_client, it):
    Warehouse.objects.create(name="CD Campinas")
    response = _post(logged_client, {"name": "cd campinas", "verticals": [it.id]})
    assert response.status_code == 400
    assert "name" in response.json()


def test_list_filters_and_search(logged_client, storage):
    Warehouse.objects.create(name="CD Campinas", city="Campinas")
    Warehouse.objects.create(name="CD Barueri", ownership="outsourced", service_provider=storage)
    Warehouse.objects.create(name="CD Recife", is_active=False)
    names = lambda r: [w["name"] for w in r.json()["results"]]  # noqa: E731
    assert names(logged_client.get(URL)) == ["CD Barueri", "CD Campinas", "CD Recife"]
    assert names(logged_client.get(URL, {"ownership": "outsourced"})) == ["CD Barueri"]
    assert names(logged_client.get(URL, {"service_provider": storage.id})) == ["CD Barueri"]
    assert names(logged_client.get(URL, {"is_active": "false"})) == ["CD Recife"]
    assert names(logged_client.get(URL, {"search": "armagerais"})) == ["CD Barueri"]


def test_delete(logged_client):
    warehouse = Warehouse.objects.create(name="CD Campinas")
    assert logged_client.delete(f"{URL}{warehouse.id}/").status_code == 204


def test_column_filters(logged_client):
    Warehouse.objects.create(name="CD Campinas", city="Campinas", state="SP", keywords=["matriz"])
    Warehouse.objects.create(name="CD Recife", city="Recife", state="PE")
    names = lambda params: [w["name"] for w in logged_client.get(URL, params).json()["results"]]  # noqa: E731
    assert names({"name": "matriz"}) == ["CD Campinas"]
    assert names({"location": "pe"}) == ["CD Recife"]


def test_verticals_rules(logged_client, it, health):
    # At least one
    response = _post(logged_client, {"name": "CD"})
    assert "verticals" in response.json()
    response = _post(logged_client, {"name": "CD", "verticals": []})
    assert "verticals" in response.json()
    # Disabled verticals cannot be added…
    health.is_enabled = False
    health.save()
    response = _post(logged_client, {"name": "CD", "verticals": [health.id]})
    assert "verticals" in response.json()
    # …but one already served stays when editing
    warehouse = Warehouse.objects.create(name="CD Recife")
    warehouse.verticals.set([health])
    response = _patch(logged_client, warehouse, {"verticals": [health.id, it.id]})
    assert response.status_code == 200, response.json()


def test_vertical_filter_and_protection(logged_client, it, health):
    campinas = Warehouse.objects.create(name="CD Campinas")
    campinas.verticals.set([it])
    Warehouse.objects.create(name="CD Recife").verticals.set([health])
    response = logged_client.get(URL, {"vertical": it.id})
    assert [w["name"] for w in response.json()["results"]] == ["CD Campinas"]
    # A vertical served by a warehouse cannot be deleted
    response = logged_client.delete(f"/api/catalogs/verticals/{it.id}/")
    assert response.status_code == 409
