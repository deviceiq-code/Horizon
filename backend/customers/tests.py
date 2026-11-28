import pytest
from django.contrib.auth import get_user_model

from users.testing import make_account_manager

from .models import Customer
from .tax_ids import brazilian_tax_id_kind, is_valid_cnpj, is_valid_cpf, normalize_tax_id

URL = "/api/customers/"

# Valid test documents
CNPJ = "11222333000181"
CNPJ_ALPHANUMERIC = "12ABC34501DE35"  # official example from the Federal Revenue
CPF = "11144477735"


@pytest.fixture
def logged_client(client, db):
    user = get_user_model().objects.create_user("tester", password="strong-password-123")
    client.force_login(user)
    return client


@pytest.fixture
def managers(db):
    return {
        "ana": make_account_manager("Ana", "Souza", "ana@example.com"),
        "bruno": make_account_manager("Bruno", "Lima", "bruno@example.com"),
        "carla": make_account_manager("Carla", "Mendes", "carla@example.com"),
    }


@pytest.fixture
def ana(managers):
    return managers["ana"]


@pytest.fixture
def customers(managers):
    trans = Customer.objects.create(
        name="Transportes Rápidos Ltda", trade_name="TransRápido", tax_id=CNPJ,
        city="Campinas", state="SP", primary_account_manager=managers["ana"],
    )  # fmt: skip
    trans.secondary_account_managers.set([managers["carla"], managers["bruno"]])
    return [
        trans,
        Customer.objects.create(
            name="Alpha Equipamentos S.A.", tax_id=CNPJ_ALPHANUMERIC, city="Curitiba", state="PR",
            primary_account_manager=managers["bruno"],
        ),
        Customer.objects.create(
            name="Maria Oliveira", tax_id=CPF, city="Recife", state="PE", is_active=False,
            primary_account_manager=managers["carla"],
        ),
    ]  # fmt: skip


def _post(client, data):
    return client.post(URL, data, content_type="application/json")


def _patch(client, pk, data):
    return client.patch(f"{URL}{pk}/", data, content_type="application/json")


# --- Tax ID validation (pure functions) ------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("11.222.333/0001-81", "cnpj"),
        ("12.ABC.345/01DE-35", "cnpj"),
        ("12.abc.345/01de-35", "cnpj"),
        ("111.444.777-35", "cpf"),
        ("11.222.333/0001-82", None),
        ("12ABC34501DE36", None),
        ("111.444.777-36", None),
        ("00000000000000", None),
        ("11111111111", None),
        ("123", None),
        ("", None),
    ],
)
def test_brazilian_tax_id_kind(value, kind):
    assert brazilian_tax_id_kind(value) == kind


def test_cnpj_check_digits_must_be_numeric():
    assert not is_valid_cnpj("12ABC34501DEAB")


def test_cpf_must_be_numeric():
    assert not is_valid_cpf("1114447773A")


def test_normalize_tax_id():
    assert normalize_tax_id(" 12.abc.345/01de-35 ") == "12ABC34501DE35"


# --- API: access, list, search, ordering -----------------------------------------------------


@pytest.mark.django_db
def test_requires_login(client):
    assert client.get(URL).status_code == 403


def test_list_includes_account_managers(logged_client, customers, managers):
    results = logged_client.get(URL).json()["results"]
    assert [c["name"] for c in results] == [
        "Alpha Equipamentos S.A.",
        "Maria Oliveira",
        "Transportes Rápidos Ltda",
    ]
    trans = results[2]
    assert trans["primary_account_manager"] == managers["ana"].pk
    assert trans["primary_account_manager_name"] == "Ana Souza"
    assert sorted(trans["secondary_account_managers"]) == sorted(
        [managers["bruno"].pk, managers["carla"].pk]
    )
    # Detail sorted by name, for display
    assert [m["full_name"] for m in trans["secondary_account_managers_detail"]] == [
        "Bruno Lima",
        "Carla Mendes",
    ]
    assert results[0]["secondary_account_managers_detail"] == []


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("transrápido", ["Transportes Rápidos Ltda"]),
        ("curitiba", ["Alpha Equipamentos S.A."]),
        ("ana souza", ["Transportes Rápidos Ltda"]),  # primary
        # Bruno is primary of Alpha and secondary of Trans: each customer once
        ("bruno", ["Alpha Equipamentos S.A.", "Transportes Rápidos Ltda"]),
        ("11.222.333/0001-81", ["Transportes Rápidos Ltda"]),
        ("11222333", ["Transportes Rápidos Ltda"]),
        ("12.abc.345", ["Alpha Equipamentos S.A."]),
        ("111.444.777-35", ["Maria Oliveira"]),
    ],
)
def test_search(logged_client, customers, term, expected):
    results = logged_client.get(URL, {"search": term}).json()["results"]
    assert [c["name"] for c in results] == expected


def test_ordering_by_primary_account_manager(logged_client, customers):
    results = logged_client.get(URL, {"ordering": "-primary_account_manager__first_name"}).json()[
        "results"
    ]
    assert [c["primary_account_manager_name"] for c in results] == [
        "Carla Mendes",
        "Bruno Lima",
        "Ana Souza",
    ]


# --- Written through business entities ------------------------------------------------------


def test_read_only_here(logged_client, customers, ana):
    """Customers are a role of business entities: written at /api/business-entities/."""
    assert _post(logged_client, {"name": "X", "tax_id": CNPJ}).status_code == 405
    assert logged_client.delete(f"{URL}{customers[0].pk}/").status_code == 405


def test_active_in_the_role_and_as_an_entity(logged_client, customers):
    names = lambda params: [c["name"] for c in logged_client.get(URL, params).json()["results"]]  # noqa: E731
    assert names({"is_active": "true"}) == ["Alpha Equipamentos S.A.", "Transportes Rápidos Ltda"]
    # The entity deactivated: no longer an active customer, though the role is
    alpha = customers[1].entity
    alpha.is_active = False
    alpha.save()
    assert names({"is_active": "true"}) == ["Transportes Rápidos Ltda"]
    assert names({"is_active": "false"}) == ["Alpha Equipamentos S.A.", "Maria Oliveira"]


def test_column_filters(logged_client, customers):
    names = lambda params: [c["name"] for c in logged_client.get(URL, params).json()["results"]]  # noqa: E731
    assert names({"name": "transrápido"}) == ["Transportes Rápidos Ltda"]
    assert names({"tax_id": "111.444"}) == ["Maria Oliveira"]
    assert names({"location": "PR"}) == ["Alpha Equipamentos S.A."]
    assert names({"location": "recif"}) == ["Maria Oliveira"]
