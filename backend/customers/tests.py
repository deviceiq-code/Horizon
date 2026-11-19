import pytest
from django.contrib.auth import get_user_model

from account_managers.models import AccountManager

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
def ana(db):
    return AccountManager.objects.create(full_name="Ana Souza", email="ana@example.com")


@pytest.fixture
def customers(ana):
    return [
        Customer.objects.create(
            name="Transportes Rápidos Ltda", trade_name="TransRápido", tax_id=CNPJ,
            city="Campinas", state="SP", account_manager=ana,
        ),
        Customer.objects.create(
            name="Alpha Equipamentos S.A.", tax_id=CNPJ_ALPHANUMERIC, city="Curitiba", state="PR",
        ),
        Customer.objects.create(
            name="Maria Oliveira", tax_id=CPF, city="Recife", state="PE", is_active=False,
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


def test_list_includes_account_manager_name(logged_client, customers):
    results = logged_client.get(URL).json()["results"]
    assert [c["name"] for c in results] == [
        "Alpha Equipamentos S.A.",
        "Maria Oliveira",
        "Transportes Rápidos Ltda",
    ]
    trans = results[2]
    assert trans["account_manager_name"] == "Ana Souza"
    assert results[0]["account_manager_name"] is None


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("transrápido", ["Transportes Rápidos Ltda"]),
        ("curitiba", ["Alpha Equipamentos S.A."]),
        ("ana souza", ["Transportes Rápidos Ltda"]),
        ("11.222.333/0001-81", ["Transportes Rápidos Ltda"]),
        ("11222333", ["Transportes Rápidos Ltda"]),
        ("12.abc.345", ["Alpha Equipamentos S.A."]),
        ("111.444.777-35", ["Maria Oliveira"]),
    ],
)
def test_search(logged_client, customers, term, expected):
    results = logged_client.get(URL, {"search": term}).json()["results"]
    assert [c["name"] for c in results] == expected


@pytest.mark.parametrize("ordering", ["account_manager__full_name", "-account_manager__full_name"])
def test_customers_without_account_manager_sort_last(logged_client, customers, ordering):
    results = logged_client.get(URL, {"ordering": ordering}).json()["results"]
    assert [c["account_manager_name"] for c in results] == ["Ana Souza", None, None]


# --- API: create / update / delete -----------------------------------------------------------


def test_create_normalizes_fields(logged_client, ana):
    r = _post(
        logged_client,
        {
            "name": "  Beta   Locações  Ltda ",
            "tax_id": "11.222.333/0001-81",
            "email": " Contato@Beta.COM ",
            "postal_code": "13010-100",
            "state": "sp",
            "city": " Campinas ",
            "account_manager": ana.pk,
        },
    )
    assert r.status_code == 201, r.json()
    c = Customer.objects.get(pk=r.json()["id"])
    assert (c.name, c.tax_id, c.email, c.postal_code, c.state, c.city, c.country) == (
        "Beta Locações Ltda",
        CNPJ,
        "contato@beta.com",
        "13010100",
        "SP",
        "Campinas",
        "BR",
    )
    assert c.account_manager == ana
    assert c.is_active is True


def test_create_with_alphanumeric_cnpj(logged_client):
    r = _post(logged_client, {"name": "Gama S.A.", "tax_id": "12.abc.345/01de-35"})
    assert r.status_code == 201
    assert r.json()["tax_id"] == CNPJ_ALPHANUMERIC


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"name": "", "tax_id": CNPJ}, "name"),
        ({"name": "X", "tax_id": ""}, "tax_id"),
        ({"name": "X", "tax_id": "11.222.333/0001-82"}, "tax_id"),
        ({"name": "X", "tax_id": CNPJ, "postal_code": "1234"}, "postal_code"),
        ({"name": "X", "tax_id": CNPJ, "state": "XX"}, "state"),
        ({"name": "X", "tax_id": CNPJ, "email": "not-an-email"}, "email"),
        ({"name": "X", "tax_id": CNPJ, "country": "Brazil"}, "country"),
        ({"name": "X", "tax_id": CNPJ, "account_manager": 999999}, "account_manager"),
    ],
)
def test_create_validation(logged_client, db, data, field):
    r = _post(logged_client, data)
    assert r.status_code == 400
    assert field in r.json()


def test_foreign_customer_tax_id_is_free_form(logged_client):
    r = _post(
        logged_client,
        {"name": "Acme Inc.", "tax_id": "12-3456789", "country": "us", "postal_code": "94105"},
    )
    assert r.status_code == 201, r.json()
    assert (r.json()["tax_id"], r.json()["country"]) == ("123456789", "US")


def test_tax_id_must_be_unique_per_country(logged_client, customers):
    r = _post(logged_client, {"name": "Other", "tax_id": "11.222.333/0001-81"})
    assert r.status_code == 400
    assert r.json()["tax_id"] == ["A customer with this tax ID already exists."]
    # Same number in another country is a different document
    assert (
        _post(logged_client, {"name": "Other", "tax_id": CNPJ, "country": "PT"}).status_code == 201
    )


def test_update_keeps_own_tax_id(logged_client, customers):
    trans = customers[0]
    r = _patch(logged_client, trans.pk, {"tax_id": "11.222.333/0001-81", "is_active": False})
    assert r.status_code == 200
    trans.refresh_from_db()
    assert trans.is_active is False


def test_update_can_remove_account_manager(logged_client, customers):
    trans = customers[0]
    assert _patch(logged_client, trans.pk, {"account_manager": None}).status_code == 200
    trans.refresh_from_db()
    assert trans.account_manager is None


def test_delete(logged_client, customers):
    assert logged_client.delete(f"{URL}{customers[2].pk}/").status_code == 204
    assert Customer.objects.count() == 2


# --- Relationship with account managers ------------------------------------------------------


def test_account_manager_with_customers_cannot_be_deleted(logged_client, customers, ana):
    r = logged_client.delete(f"/api/account-managers/{ana.pk}/")
    assert r.status_code == 409
    assert r.json()["detail"] == "This account manager has customers and cannot be deleted."
    assert AccountManager.objects.filter(pk=ana.pk).exists()


def test_validation_messages_follow_user_language(logged_client, db):
    logged_client.patch(
        "/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json"
    )
    r = _post(logged_client, {"name": "X", "tax_id": "123"})
    assert r.json()["tax_id"] == ["Informe um CPF ou CNPJ válido."]
