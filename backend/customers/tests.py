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
            "primary_account_manager": ana.pk,
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
    assert c.primary_account_manager == ana
    assert c.secondary_account_managers.count() == 0
    assert c.is_active is True


def test_create_with_secondary_account_managers(logged_client, managers):
    r = _post(
        logged_client,
        {
            "name": "Beta Locações",
            "tax_id": CNPJ,
            "primary_account_manager": managers["ana"].pk,
            "secondary_account_managers": [managers["bruno"].pk, managers["carla"].pk],
        },
    )
    assert r.status_code == 201, r.json()
    c = Customer.objects.get(pk=r.json()["id"])
    assert set(c.secondary_account_managers.all()) == {managers["bruno"], managers["carla"]}


def test_create_with_alphanumeric_cnpj(logged_client, ana):
    r = _post(
        logged_client,
        {"name": "Gama S.A.", "tax_id": "12.abc.345/01de-35", "primary_account_manager": ana.pk},
    )
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
        ({"primary_account_manager": 999999}, "primary_account_manager"),
        ({"secondary_account_managers": [999999]}, "secondary_account_managers"),
    ],
)
def test_create_validation(logged_client, ana, data, field):
    valid = {"name": "X", "tax_id": CNPJ, "primary_account_manager": ana.pk}
    r = _post(logged_client, {**valid, **data})
    assert r.status_code == 400
    assert field in r.json()


def test_primary_account_manager_is_required(logged_client, db):
    r = _post(logged_client, {"name": "X", "tax_id": CNPJ})
    assert r.status_code == 400
    assert "primary_account_manager" in r.json()
    r = _post(logged_client, {"name": "X", "tax_id": CNPJ, "primary_account_manager": None})
    assert r.status_code == 400
    assert "primary_account_manager" in r.json()


def test_primary_cannot_also_be_secondary(logged_client, managers):
    r = _post(
        logged_client,
        {
            "name": "X",
            "tax_id": CNPJ,
            "primary_account_manager": managers["ana"].pk,
            "secondary_account_managers": [managers["bruno"].pk, managers["ana"].pk],
        },
    )
    assert r.status_code == 400
    assert r.json()["secondary_account_managers"] == [
        "The primary account manager cannot also be a secondary one."
    ]


def test_changing_primary_to_a_current_secondary_is_rejected(logged_client, customers, managers):
    # Trans: primary Ana, secondaries Bruno and Carla. Promoting Bruno alone conflicts…
    trans = customers[0]
    r = _patch(logged_client, trans.pk, {"primary_account_manager": managers["bruno"].pk})
    assert r.status_code == 400
    # …but swapping in the same request is fine
    r = _patch(
        logged_client,
        trans.pk,
        {
            "primary_account_manager": managers["bruno"].pk,
            "secondary_account_managers": [managers["ana"].pk, managers["carla"].pk],
        },
    )
    assert r.status_code == 200, r.json()
    trans.refresh_from_db()
    assert trans.primary_account_manager == managers["bruno"]
    assert set(trans.secondary_account_managers.all()) == {managers["ana"], managers["carla"]}


def test_foreign_customer_tax_id_is_free_form(logged_client, ana):
    r = _post(
        logged_client,
        {
            "name": "Acme Inc.",
            "tax_id": "12-3456789",
            "country": "us",
            "postal_code": "94105",
            "primary_account_manager": ana.pk,
        },
    )
    assert r.status_code == 201, r.json()
    assert (r.json()["tax_id"], r.json()["country"]) == ("123456789", "US")


def test_tax_id_must_be_unique_per_country(logged_client, customers, ana):
    base = {"name": "Other", "primary_account_manager": ana.pk}
    r = _post(logged_client, {**base, "tax_id": "11.222.333/0001-81"})
    assert r.status_code == 400
    assert r.json()["tax_id"] == ["A customer with this tax ID already exists."]
    # Same number in another country is a different document
    assert _post(logged_client, {**base, "tax_id": CNPJ, "country": "PT"}).status_code == 201


def test_update_keeps_own_tax_id(logged_client, customers):
    trans = customers[0]
    r = _patch(logged_client, trans.pk, {"tax_id": "11.222.333/0001-81", "is_active": False})
    assert r.status_code == 200
    trans.refresh_from_db()
    assert trans.is_active is False


def test_update_without_account_managers_keeps_them(logged_client, customers, managers):
    trans = customers[0]
    assert _patch(logged_client, trans.pk, {"city": "Jundiaí"}).status_code == 200
    trans.refresh_from_db()
    assert trans.primary_account_manager == managers["ana"]
    assert trans.secondary_account_managers.count() == 2


def test_update_can_clear_secondary_account_managers(logged_client, customers):
    trans = customers[0]
    r = _patch(logged_client, trans.pk, {"secondary_account_managers": []})
    assert r.status_code == 200
    assert trans.secondary_account_managers.count() == 0


def test_primary_account_manager_cannot_be_removed(logged_client, customers):
    r = _patch(logged_client, customers[0].pk, {"primary_account_manager": None})
    assert r.status_code == 400


def test_delete(logged_client, customers):
    assert logged_client.delete(f"{URL}{customers[2].pk}/").status_code == 204
    assert Customer.objects.count() == 2


# --- Account managers are users with the role ----------------------------------------------


def test_only_account_managers_can_be_chosen(logged_client, customers, managers):
    from django.contrib.auth import get_user_model

    plain = get_user_model().objects.create_user("plain", password="Plain-user-2026")
    r = logged_client.patch(
        f"{URL}{customers[0].pk}/",
        {"primary_account_manager": plain.pk, "secondary_account_managers": [plain.pk]},
        content_type="application/json",
    )
    assert r.status_code == 400
    assert r.json()["primary_account_manager"] == ["This user is not an account manager."]
    assert r.json()["secondary_account_managers"] == ["This user is not an account manager."]


def test_validation_messages_follow_user_language(logged_client, managers):
    logged_client.patch(
        "/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json"
    )
    ana = managers["ana"]
    r = _post(logged_client, {"name": "X", "tax_id": "123", "primary_account_manager": ana.pk})
    assert r.json()["tax_id"] == ["Informe um CPF ou CNPJ válido."]
    r = _post(
        logged_client,
        {
            "name": "X",
            "tax_id": CNPJ,
            "primary_account_manager": ana.pk,
            "secondary_account_managers": [ana.pk],
        },
    )
    assert r.json()["secondary_account_managers"] == [
        "O account manager principal não pode ser também secundário."
    ]


def test_keywords_normalized_and_searchable(logged_client, ana):
    r = _post(
        logged_client,
        {
            "name": "Acme Ltda",
            "tax_id": CNPJ,
            "primary_account_manager": ana.pk,
            "keywords": [" Agro ", "AGRO", "Linha   Amarela"],
        },
    )
    assert r.status_code == 201, r.json()
    assert r.json()["keywords"] == ["agro", "linha amarela"]
    found = logged_client.get(URL, {"search": "Amarela"}).json()["results"]
    assert [c["name"] for c in found] == ["Acme Ltda"]
    # Optional: an empty list without them
    assert _patch(logged_client, r.json()["id"], {"keywords": []}).json()["keywords"] == []


def test_column_filters(logged_client, customers):
    names = lambda params: [c["name"] for c in logged_client.get(URL, params).json()["results"]]  # noqa: E731
    assert names({"name": "transrápido"}) == ["Transportes Rápidos Ltda"]
    assert names({"tax_id": "111.444"}) == ["Maria Oliveira"]
    assert names({"location": "PR"}) == ["Alpha Equipamentos S.A."]
    assert names({"location": "recif"}) == ["Maria Oliveira"]
