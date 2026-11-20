import pytest

from catalogs.models import AssetClass, SubVertical
from customers.models import Customer
from efmv.models import EfmvAnalysis, format_code
from pricing.models import AveragePrice
from pricing.testing import _new_version, _payload, _post
from users.testing import make_account_manager

URL = "/api/efmv-analyses/"
CNPJ = "11.222.333/0001-81"
CNPJ_2 = "11.444.777/0001-61"


@pytest.fixture
def managers(db):
    return {
        "ana": make_account_manager("Ana", "Lima", "ana@example.com"),
        "bruno": make_account_manager("Bruno", "Reis", "bruno@example.com"),
    }


@pytest.fixture
def customers(managers):
    acme = Customer.objects.create(
        name="Acme Ltda", tax_id=CNPJ, primary_account_manager=managers["ana"]
    )
    beta = Customer.objects.create(
        name="Beta S.A.", tax_id=CNPJ_2, primary_account_manager=managers["bruno"]
    )
    beta.secondary_account_managers.set([managers["ana"]])
    return {"acme": acme, "beta": beta}


@pytest.fixture
def prices(logged_client, catalog):
    """An excavator (100,000; terms 12/24/36) and a tractor (50,000; terms 12/24)."""
    farm = SubVertical.objects.create(
        vertical=catalog["yellow"].vertical,
        name="Farm",
        risk="low",
        allowed_terms=[12, 24],
        recommended_term=24,
    )
    tractors = AssetClass.objects.create(name="Tractors", sub_vertical=farm)
    r = _post(
        logged_client,
        _payload(
            catalog,
            asset_class=tractors.pk,
            specs={},
            model="Tractor 5E",
            manufacturer=catalog["deere"].pk,
            original_value="50000.00",
            points=[
                {"term_months": 12, "mode": "percent", "amount": "80"},
                {"term_months": 24, "mode": "percent", "amount": "60"},
            ],
        ),
    )
    assert r.status_code == 201, r.json()
    r2 = _post(logged_client, _payload(catalog))
    assert r2.status_code == 201, r2.json()
    return {"tractor": r.json()["id"], "excavator": r2.json()["id"]}


def body(managers, customers, prices, **overrides):
    return {
        "account_manager": managers["ana"].pk,
        "customer": customers["acme"].pk,
        "scenarios": [
            {
                "name": "Base",
                "term_months": 24,
                "scope": "Yellow line fleet",
                "items": [
                    {"average_price": prices["excavator"], "quantity": 2},
                    {"average_price": prices["tractor"], "quantity": 1},
                ],
            }
        ],
        **overrides,
    }


def post(client, data):
    return client.post(URL, data, content_type="application/json")


def test_format_code():
    assert format_code(2026, 7) == "EFMV-2026-0007"


def test_requires_login(client, db):
    assert client.get(URL).status_code == 403


def test_create_with_totals(logged_client, managers, customers, prices):
    r = post(logged_client, body(managers, customers, prices))
    assert r.status_code == 201, r.json()
    data = r.json()
    assert data["code"].startswith("EFMV-") and data["code"].endswith("-0001")
    assert data["account_manager_detail"]["full_name"] == "Ana Lima"
    assert data["customer_detail"]["name"] == "Acme Ltda"
    (scenario,) = data["scenarios"]
    assert scenario["name"] == "Base" and scenario["term_months"] == 24
    assert [i["line_total"] for i in scenario["items"]] == ["200000.00", "50000.00"]
    assert scenario["items"][0]["terms"] == [12, 24, 36]
    assert scenario["totals"] == {
        "lo": "250000.00",
        "efmv_percent": None,
        "hw_percent": "100.00",
        "sw_percent": "0.00",
        "sv_percent": "0.00",
    }
    # The next one gets the next number
    r = post(logged_client, body(managers, customers, prices))
    assert r.json()["code"].endswith("-0002")


def test_at_least_one_scenario(logged_client, managers, customers, prices):
    r = post(logged_client, body(managers, customers, prices, scenarios=[]))
    assert r.status_code == 400 and "scenarios" in r.json()
    r = post(
        logged_client, {"account_manager": managers["ana"].pk, "customer": customers["acme"].pk}
    )
    assert r.status_code == 400 and "scenarios" in r.json()


def test_scenario_names_are_distinct(logged_client, managers, customers, prices):
    scenario = {"name": "Base", "term_months": 12, "items": []}
    r = post(
        logged_client,
        body(managers, customers, prices, scenarios=[scenario, {**scenario, "name": " base "}]),
    )
    assert r.status_code == 400
    assert "1" in r.json()["scenarios"]


def test_term_beyond_the_curve_is_refused(logged_client, managers, customers, prices):
    data = body(managers, customers, prices)
    data["scenarios"][0]["term_months"] = 36  # the tractor's curve stops at 24
    r = post(logged_client, data)
    assert r.status_code == 400
    errors = r.json()["scenarios"]["0"]["items"]
    assert list(errors) == ["1"]
    assert "24" in errors["1"]["average_price"][0]


def test_same_asset_twice_is_refused(logged_client, managers, customers, prices):
    data = body(managers, customers, prices)
    data["scenarios"][0]["items"].append({"average_price": prices["excavator"], "quantity": 1})
    r = post(logged_client, data)
    assert r.status_code == 400
    assert "2" in r.json()["scenarios"]["0"]["items"]


def test_account_manager_must_serve_the_customer(logged_client, managers, customers, prices):
    # Bruno does not serve Acme
    r = post(logged_client, body(managers, customers, prices, account_manager=managers["bruno"].pk))
    assert r.status_code == 400 and "customer" in r.json()
    # Ana is a secondary account manager of Beta
    r = post(logged_client, body(managers, customers, prices, customer=customers["beta"].pk))
    assert r.status_code == 201, r.json()


def test_account_manager_must_have_the_role(logged_client, user, managers, customers, prices):
    r = post(logged_client, body(managers, customers, prices, account_manager=user.pk))
    assert r.status_code == 400 and "account_manager" in r.json()


def test_uses_the_current_version(logged_client, managers, customers, prices, catalog):
    r = post(logged_client, body(managers, customers, prices))
    analysis = r.json()["id"]
    newer = _new_version(logged_client, catalog, prices["excavator"], "120000.00")
    data = logged_client.get(f"{URL}{analysis}/").json()
    item = data["scenarios"][0]["items"][0]
    assert item["average_price"] == newer
    assert item["original_value"] == "120000.00"
    assert data["scenarios"][0]["totals"]["lo"] == "290000.00"


def test_deleted_price_is_flagged_and_left_out(logged_client, managers, customers, prices):
    analysis = post(logged_client, body(managers, customers, prices)).json()["id"]
    assert (
        logged_client.delete(f"/api/average-prices/{prices['tractor']}/history/").status_code == 204
    )
    scenario = logged_client.get(f"{URL}{analysis}/").json()["scenarios"][0]
    assert [i["available"] for i in scenario["items"]] == [True, False]
    assert scenario["totals"]["lo"] == "200000.00"
    # A deleted price cannot be added
    data = body(managers, customers, prices)
    r = post(logged_client, data)
    assert r.status_code == 400


def test_edit_replaces_scenarios(logged_client, managers, customers, prices):
    analysis = post(logged_client, body(managers, customers, prices)).json()
    data = body(
        managers,
        customers,
        prices,
        scenarios=[
            {
                "name": "Short",
                "term_months": 12,
                "items": [{"average_price": prices["tractor"], "quantity": 3}],
            },
            {"name": "Long", "term_months": 36, "scope": "", "items": []},
        ],
    )
    r = logged_client.put(f"{URL}{analysis['id']}/", data, content_type="application/json")
    assert r.status_code == 200, r.json()
    assert r.json()["code"] == analysis["code"]
    assert [s["name"] for s in r.json()["scenarios"]] == ["Short", "Long"]
    assert r.json()["scenarios"][0]["totals"]["lo"] == "150000.00"
    assert r.json()["scenarios"][1]["totals"]["hw_percent"] is None


def test_list_search_and_filters(logged_client, managers, customers, prices):
    first = post(logged_client, body(managers, customers, prices)).json()
    post(logged_client, body(managers, customers, prices, customer=customers["beta"].pk))
    rows = logged_client.get(URL).json()["results"]
    assert len(rows) == 2
    assert rows[1]["scenario_names"] == ["Base"]
    found = logged_client.get(URL, {"search": first["code"].lower()}).json()["results"]
    assert [r["id"] for r in found] == [first["id"]]
    found = logged_client.get(URL, {"search": "beta"}).json()["results"]
    assert [r["customer_detail"]["name"] for r in found] == ["Beta S.A."]
    found = logged_client.get(URL, {"customer": customers["acme"].pk}).json()["results"]
    assert [r["id"] for r in found] == [first["id"]]
    codes = [r["code"] for r in logged_client.get(URL, {"ordering": "code"}).json()["results"]]
    assert codes == sorted(codes)


def test_delete(logged_client, managers, customers, prices):
    analysis = post(logged_client, body(managers, customers, prices)).json()
    assert logged_client.delete(f"{URL}{analysis['id']}/").status_code == 204
    assert not EfmvAnalysis.objects.exists()


def test_scenario_preview(logged_client, prices):
    r = post_preview = logged_client.post(
        f"{URL}scenario-preview/",
        {"term_months": 36, "items": [
            {"average_price": prices["excavator"], "quantity": 1},
            {"average_price": prices["tractor"], "quantity": 1},
        ]},
        content_type="application/json",
    )  # fmt: skip
    assert post_preview.status_code == 200, r.json()
    data = r.json()
    assert [i["out_of_curve"] for i in data["items"]] == [False, True]
    assert data["totals"]["lo"] == "100000.00"


def test_price_in_an_analysis_is_kept(logged_client, managers, customers, prices):
    post(logged_client, body(managers, customers, prices))
    assert AveragePrice.objects.filter(pk=prices["excavator"]).exists()


def test_customers_filtered_by_account_manager(logged_client, managers, customers):
    names = lambda params: [  # noqa: E731
        c["name"] for c in logged_client.get("/api/customers/", params).json()["results"]
    ]
    assert names({"account_manager": managers["ana"].pk}) == ["Acme Ltda", "Beta S.A."]
    assert names({"account_manager": managers["bruno"].pk}) == ["Beta S.A."]
    customers["acme"].is_active = False
    customers["acme"].save()
    assert names({"account_manager": managers["ana"].pk, "is_active": "true"}) == ["Beta S.A."]
