import pytest
from django.contrib.auth import get_user_model

from catalogs.models import Vertical
from customers.models import Customer
from efmv.models import EfmvAnalysis
from inventory.models import Warehouse
from service_providers.models import ServiceProvider
from users.testing import make_account_manager

from . import hierarchy
from .models import BusinessEntity, Buyer

URL = "/api/business-entities/"

CNPJ = "11222333000181"  # head office (0001) of root 11222333
BRANCH = "11222333000262"  # branch 0002, same root
BRANCH_3 = "11222333000343"
OTHER = "44775566000160"
CNPJ_ALPHANUMERIC = "12ABC34501DE35"
CPF = "11144477735"


@pytest.fixture
def logged_client(client, db):
    user = get_user_model().objects.create_user("tester", password="strong-password-123")
    client.force_login(user)
    return client


@pytest.fixture
def ana(db):
    return make_account_manager("Ana", "Souza", "ana@example.com")


@pytest.fixture
def bruno(db):
    return make_account_manager("Bruno", "Lima", "bruno@example.com")


def _post(client, data):
    return client.post(URL, data, content_type="application/json")


def _patch(client, pk, data):
    return client.patch(f"{URL}{pk}/", data, content_type="application/json")


def _names(client, params=None):
    return [e["name"] for e in client.get(URL, params or {}).json()["results"]]


# --- Hierarchy (pure) -------------------------------------------------------------------------


def test_cycles_are_found_at_any_depth():
    parents = {1: None, 2: 1, 3: 2, 4: 3}.get  # 1 ← 2 ← 3 ← 4
    assert hierarchy.creates_cycle(1, 4, parents)  # 1 under its own branch's branch
    assert hierarchy.creates_cycle(2, 2, parents)  # itself
    assert not hierarchy.creates_cycle(4, 1, parents)
    assert not hierarchy.creates_cycle(None, 1, parents)  # a new entity never closes one
    assert hierarchy.group_root(4, parents) == 1
    assert hierarchy.descendants(2, [(1, None), (2, 1), (3, 2), (4, 3), (5, 1)]) == {2, 3, 4}


def test_cnpj_root():
    assert hierarchy.cnpj_root("BR", BRANCH) == "11222333"
    assert hierarchy.cnpj_root("BR", CPF) is None
    assert hierarchy.cnpj_root("US", CNPJ) is None
    assert hierarchy.cnpj_root("BR", CNPJ_ALPHANUMERIC) == "12ABC345"
    assert hierarchy.is_head_office_cnpj(CNPJ) and not hierarchy.is_head_office_cnpj(BRANCH)


# --- The entity -------------------------------------------------------------------------------


def test_requires_login(client, db):
    assert client.get(URL).status_code == 403


def test_create_normalizes_fields_and_starts_without_roles(logged_client):
    r = _post(
        logged_client,
        {
            "name": "  Beta   Locações  Ltda ",
            "tax_id": "11.222.333/0001-81",
            "contact_name": " Ana   Souza ",
            "email": " Contato@Beta.COM ",
            "postal_code": "13010-100",
            "state": "sp",
            "city": " Campinas ",
            "keywords": [" Agro ", "AGRO", "Linha   Amarela"],
        },
    )
    assert r.status_code == 201, r.json()
    data = r.json()
    assert (data["name"], data["tax_id"], data["email"]) == (
        "Beta Locações Ltda",
        CNPJ,
        "contato@beta.com",
    )
    assert (data["postal_code"], data["state"], data["city"]) == ("13010100", "SP", "Campinas")
    assert data["contact_name"] == "Ana Souza"
    assert data["keywords"] == ["agro", "linha amarela"]
    assert data["roles"] == []
    assert data["customer"] is None and data["service_provider"] is None
    assert data["parent"] is None and data["group_detail"] is None


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"name": ""}, "name"),
        ({"tax_id": ""}, "tax_id"),
        ({"tax_id": "11.222.333/0001-82"}, "tax_id"),
        ({"postal_code": "1234"}, "postal_code"),
        ({"state": "XX"}, "state"),
        ({"email": "not-an-email"}, "email"),
        ({"country": "Brazil"}, "country"),
    ],
)
def test_create_validation(logged_client, data, field):
    r = _post(logged_client, {"name": "X", "tax_id": CNPJ, **data})
    assert r.status_code == 400
    assert field in r.json()


def test_tax_id_unique_per_country_and_free_abroad(logged_client):
    assert _post(logged_client, {"name": "A", "tax_id": CNPJ}).status_code == 201
    r = _post(logged_client, {"name": "B", "tax_id": CNPJ})
    assert r.status_code == 400 and "tax_id" in r.json()
    # Abroad: free-form, not CPF/CNPJ-checked
    assert (
        _post(logged_client, {"name": "C", "tax_id": "ab-123", "country": "us"}).status_code == 201
    )
    # Alphanumeric CNPJ and CPF
    assert _post(logged_client, {"name": "D", "tax_id": CNPJ_ALPHANUMERIC}).status_code == 201
    assert _post(logged_client, {"name": "E", "tax_id": "111.444.777-35"}).status_code == 201


def test_messages_follow_user_language(logged_client):
    logged_client.patch(
        "/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json"
    )
    r = _post(logged_client, {"name": "X", "tax_id": "123"})
    assert r.json()["tax_id"] == ["Informe um CPF ou CNPJ válido."]


# --- Roles ------------------------------------------------------------------------------------


def test_roles_are_turned_on_changed_and_removed(logged_client, ana, bruno):
    r = _post(
        logged_client,
        {
            "name": "Dell Computadores do Brasil Ltda",
            "trade_name": "Dell",
            "tax_id": CNPJ,
            "customer": {
                "primary_account_manager": ana.pk,
                "secondary_account_managers": [bruno.pk],
                "contract_types": ["service_customer", "renter", "renter"],
            },
            "supplier": {"supplies": ["services", "products", "services"]},
        },
    )
    assert r.status_code == 201, r.json()
    data = r.json()
    assert data["roles"] == ["customer", "supplier"]
    assert data["customer"]["primary_account_manager_name"] == "Ana Souza"
    assert [m["full_name"] for m in data["customer"]["secondary_account_managers_detail"]] == [
        "Bruno Lima"
    ]
    # Kept in the choices' order, without repeats
    assert data["supplier"]["supplies"] == ["products", "services"]
    assert data["customer"]["contract_types"] == ["renter", "service_customer"]
    assert _names(logged_client, {"contract_type": "renter"}) == [
        "Dell Computadores do Brasil Ltda"
    ]
    assert _names(logged_client, {"contract_type": "bailee"}) == []
    pk = data["id"]
    # Another role later; one left out stays as it is
    r = _patch(logged_client, pk, {"service_provider": {"services": ["repair"]}, "buyer": {}})
    assert r.json()["roles"] == ["customer", "supplier", "service_provider", "buyer"]
    # Deactivated in one role only
    r = _patch(logged_client, pk, {"customer": {"is_active": False}})
    assert r.json()["customer"]["is_active"] is False and r.json()["is_active"] is True
    # Removed
    r = _patch(logged_client, pk, {"supplier": None, "buyer": None})
    assert r.json()["roles"] == ["customer", "service_provider"]
    assert not Buyer.objects.exists()


@pytest.mark.parametrize(
    ("roles", "error"),
    [
        ({"customer": {}}, ("customer", "primary_account_manager")),
        (
            {"customer": {"primary_account_manager": 999999}},
            ("customer", "primary_account_manager"),
        ),
        ({"service_provider": {}}, ("service_provider", "services")),
        ({"service_provider": {"services": []}}, ("service_provider", "services")),
        ({"service_provider": {"services": ["catering"]}}, ("service_provider", "services")),
        ({"supplier": {"supplies": []}}, ("supplier", "supplies")),
        ({"supplier": {}}, ("supplier", "supplies")),
        ({"customer": {"contract_types": ["sale"]}}, ("customer", "contract_types")),
    ],
)
def test_roles_validation(logged_client, roles, error):
    r = _post(logged_client, {"name": "X", "tax_id": CNPJ, **roles})
    assert r.status_code == 400
    role, field = error
    assert field in r.json()[role]


def test_only_account_managers_and_primary_not_secondary(logged_client, ana, db):
    plain = get_user_model().objects.create_user("plain", first_name="Plain")
    r = _post(
        logged_client,
        {"name": "X", "tax_id": CNPJ, "customer": {"primary_account_manager": plain.pk}},
    )
    assert "primary_account_manager" in r.json()["customer"]
    r = _post(
        logged_client,
        {
            "name": "X",
            "tax_id": CNPJ,
            "customer": {
                "primary_account_manager": ana.pk,
                "secondary_account_managers": [ana.pk],
            },
        },
    )
    assert "secondary_account_managers" in r.json()["customer"]


def test_a_role_in_use_cannot_be_removed(logged_client, ana):
    customer = Customer.objects.create(name="Acme", tax_id=CNPJ, primary_account_manager=ana)
    EfmvAnalysis.objects.create(
        account_manager=ana,
        customer=customer,
        vertical=Vertical.objects.create(name="IT"),
        year=2026,
        sequence=1,
        created_by=ana,
        updated_by=ana,
    )
    r = _patch(logged_client, customer.entity_id, {"customer": None})
    assert r.status_code == 409
    assert "Deactivate" in r.json()["detail"]
    assert Customer.objects.filter(pk=customer.pk).exists()
    # Nor the entity
    assert logged_client.delete(f"{URL}{customer.entity_id}/").status_code == 409


def test_warehouses_keep_warehousing_and_their_provider(logged_client):
    provider = ServiceProvider.objects.create(
        name="Armazéns", tax_id=CNPJ, services=["warehousing"]
    )
    Warehouse.objects.create(name="CD Barueri", ownership="outsourced", service_provider=provider)
    pk = provider.entity_id
    r = _patch(logged_client, pk, {"service_provider": {"services": ["transport"]}})
    assert r.status_code == 400 and "services" in r.json()["service_provider"]
    assert logged_client.get(f"{URL}{pk}/").json()["service_provider"]["warehouses_count"] == 1
    assert _patch(logged_client, pk, {"service_provider": None}).status_code == 409


def test_delete_unused(logged_client, ana):
    customer = Customer.objects.create(name="Acme", tax_id=CNPJ, primary_account_manager=ana)
    assert logged_client.delete(f"{URL}{customer.entity_id}/").status_code == 204
    assert not BusinessEntity.objects.exists() and not Customer.objects.exists()


# --- Head offices and groups ------------------------------------------------------------------


def test_head_office_and_group(logged_client):
    head = _post(logged_client, {"name": "Grupo Alfa S/A", "tax_id": CNPJ}).json()["id"]
    branch = _post(logged_client, {"name": "Alfa Filial", "tax_id": BRANCH, "parent": head}).json()
    assert branch["parent_detail"]["name"] == "Grupo Alfa S/A"
    assert branch["group_detail"]["id"] == head
    sub = _post(
        logged_client, {"name": "Alfa Sub", "tax_id": BRANCH_3, "parent": branch["id"]}
    ).json()
    assert sub["group_detail"]["id"] == head  # the top of the tree, at any depth
    head_data = logged_client.get(f"{URL}{head}/").json()
    assert head_data["branches_count"] == 1 and head_data["group_detail"]["id"] == head
    assert _names(logged_client, {"group": head}) == ["Alfa Filial", "Alfa Sub", "Grupo Alfa S/A"]
    assert _names(logged_client, {"parent": head}) == ["Alfa Filial"]
    # No cycles: the head office under its own branch's branch, nor itself
    r = _patch(logged_client, head, {"parent": sub["id"]})
    assert r.status_code == 400 and "parent" in r.json()
    assert _patch(logged_client, head, {"parent": head}).status_code == 400
    # A head office with branches cannot be deleted
    r = logged_client.delete(f"{URL}{head}/")
    assert r.status_code == 409 and r.json()["detail"]
    # Free again once it has no head office
    assert _patch(logged_client, sub["id"], {"parent": None}).json()["group_detail"] is None


def test_head_office_suggested_by_the_cnpj_root(logged_client):
    suggest = lambda tax_id, **extra: logged_client.get(  # noqa: E731
        f"{URL}parent-suggestion/", {"tax_id": tax_id, **extra}
    ).json()["suggestion"]
    assert suggest(BRANCH) is None  # nothing registered with that root
    branch_3 = _post(logged_client, {"name": "Filial 3", "tax_id": BRANCH_3}).json()["id"]
    assert suggest(BRANCH)["id"] == branch_3
    head = _post(logged_client, {"name": "Matriz", "tax_id": CNPJ}).json()["id"]
    assert suggest("11.222.333/0002-62")["id"] == head  # the 0001 first
    assert suggest(BRANCH, exclude=head)["id"] == branch_3
    assert suggest(CNPJ) is None  # the head office itself
    assert suggest(CPF) is None and suggest(BRANCH, country="US") is None


# --- Lists ------------------------------------------------------------------------------------


@pytest.fixture
def entities(ana, bruno):
    trans = Customer.objects.create(
        name="Transportes Rápidos Ltda", trade_name="TransRápido", tax_id=CNPJ, city="Campinas",
        state="SP", primary_account_manager=ana,
    )  # fmt: skip
    trans.secondary_account_managers.set([bruno])
    ServiceProvider.objects.create(entity=trans.entity, services=["transport"])
    old = Customer.objects.create(
        name="Alpha Equipamentos S.A.", tax_id=OTHER, city="Curitiba", state="PR",
        primary_account_manager=bruno, is_active=False,
    )  # fmt: skip
    ServiceProvider.objects.create(name="Recicla Ltda", tax_id=CPF, services=["disposal"])
    BusinessEntity.objects.create(name="Zeta Sem Papel", tax_id=CNPJ_ALPHANUMERIC)
    return trans, old


def test_lists_by_role_with_the_role_active(logged_client, entities):
    assert _names(logged_client) == [
        "Alpha Equipamentos S.A.",
        "Recicla Ltda",
        "Transportes Rápidos Ltda",
        "Zeta Sem Papel",
    ]
    assert _names(logged_client, {"role": "customer"}) == [
        "Alpha Equipamentos S.A.",
        "Transportes Rápidos Ltda",
    ]
    # In a role's tab, "active" is the role's
    assert _names(logged_client, {"role": "customer", "is_active": "true"}) == [
        "Transportes Rápidos Ltda"
    ]
    assert _names(logged_client, {"role": "customer", "is_active": "false"}) == [
        "Alpha Equipamentos S.A."
    ]
    # In All, the entity's
    assert "Alpha Equipamentos S.A." in _names(logged_client, {"is_active": "true"})
    assert _names(logged_client, {"service": "transport"}) == ["Transportes Rápidos Ltda"]
    assert _names(logged_client, {"account_manager": entities[0].primary_account_manager_id}) == [
        "Transportes Rápidos Ltda"
    ]
    counts = logged_client.get(f"{URL}counts/").json()
    assert counts == {
        "all": 4,
        "customer": 2,
        "supplier": 0,
        "service_provider": 2,
        "buyer": 0,
    }


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("transrápido", ["Transportes Rápidos Ltda"]),
        ("curitiba", ["Alpha Equipamentos S.A."]),
        ("ana souza", ["Transportes Rápidos Ltda"]),  # the customer's account manager
        ("bruno", ["Alpha Equipamentos S.A.", "Transportes Rápidos Ltda"]),
        ("11.222.333/0001-81", ["Transportes Rápidos Ltda"]),
        ("12.abc.345", ["Zeta Sem Papel"]),
    ],
)
def test_search(logged_client, entities, term, expected):
    assert _names(logged_client, {"search": term}) == expected


def test_column_filters(logged_client, entities):
    assert _names(logged_client, {"name": "transrápido"}) == ["Transportes Rápidos Ltda"]
    assert _names(logged_client, {"tax_id": "111.444"}) == ["Recicla Ltda"]
    assert _names(logged_client, {"location": "PR"}) == ["Alpha Equipamentos S.A."]


def test_former_records_keep_pointing_to_their_roles(logged_client, entities):
    """Customers and providers keep their ids: the role reads the entity's fields."""
    trans = Customer.objects.get(pk=entities[0].pk)
    assert (trans.name, trans.trade_name, trans.city) == (
        "Transportes Rápidos Ltda",
        "TransRápido",
        "Campinas",
    )
    assert str(trans) == "TransRápido"
    listed = logged_client.get("/api/customers/").json()["results"]
    assert [c["name"] for c in listed] == ["Alpha Equipamentos S.A.", "Transportes Rápidos Ltda"]
    assert listed[1]["entity"] == trans.entity_id


def test_registers_keep_who_created_and_who_changed_them(client, ana, bruno):
    """Every register keeps the date and the user of its creation and of its last change."""
    client.force_login(ana)
    pk = _post(client, {"name": "Acme", "tax_id": CNPJ}).json()["id"]
    data = client.get(f"{URL}{pk}/").json()
    assert (data["created_by_name"], data["updated_by_name"]) == ("Ana Souza", "Ana Souza")
    assert data["created_at"] and data["updated_at"]
    client.force_login(bruno)
    data = _patch(client, pk, {"trade_name": "ACME"}).json()
    assert (data["created_by_name"], data["updated_by_name"]) == ("Ana Souza", "Bruno Lima")
    # The same in the other registers (e.g. a brand)
    r = client.post(
        "/api/catalogs/manufacturers/", {"name": "Acme Brand"}, content_type="application/json"
    )
    assert r.json()["created_by_name"] == "Bruno Lima"
