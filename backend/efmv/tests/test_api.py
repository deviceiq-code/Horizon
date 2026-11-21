from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from catalogs.models import AssetClass, SubVertical, Vertical
from customers.models import Customer
from efmv.models import EfmvAnalysis, format_code
from pricing.models import AveragePrice, PricingSettings
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
                "vertical": industry(),
                "items": [
                    {"average_price": prices["excavator"], "quantity": 2, "unit_value": "100000"},
                    {"average_price": prices["tractor"], "quantity": 1, "unit_value": "50000.00"},
                ],
            }
        ],
        **overrides,
    }


def industry():
    return Vertical.objects.get(name="Industry").pk


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
    assert [i["weight_percent"] for i in scenario["items"]] == ["80.00", "20.00"]
    assert scenario["items"][0]["terms"] == [12, 24, 36]
    assert [(spec["key"], spec["value"]) for spec in scenario["items"][0]["specs"]] == [
        ("hours", "2500"),
        ("tracks", "Steel"),
    ]
    assert scenario["totals"] == {
        "lo": "250000.00",
        # 24 months: 2 × 55,000 + 30,000 = 140,000 of 250,000
        "efmv_total": "140000.00",
        "efmv_percent": "56.00",
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
    scenario = {"name": "Base", "term_months": 12, "vertical": industry(), "items": []}
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


def test_same_asset_in_several_rows(logged_client, managers, customers, prices):
    # e.g. another value for deliveries in another state (freight and taxes)
    data = body(managers, customers, prices)
    data["scenarios"][0]["items"].append(
        {"average_price": prices["excavator"], "quantity": 1, "unit_value": "104000"}
    )
    r = post(logged_client, data)
    assert r.status_code == 201, r.json()
    items = r.json()["scenarios"][0]["items"]
    assert [(i["model"], i["unit_value"]) for i in items] == [
        ("320 GC", "100000.00"),
        ("Tractor 5E", "50000.00"),
        ("320 GC", "104000.00"),
    ]
    assert r.json()["scenarios"][0]["totals"]["lo"] == "354000.00"


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
    # The typed value is kept; the newer average price only changes how it is placed
    assert item["unit_value"] == "100000.00"
    assert (item["variation_percent"], item["position"]) == ("-16.67", "below")
    assert data["scenarios"][0]["totals"]["lo"] == "250000.00"


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
                "vertical": industry(),
                "items": [
                    {"average_price": prices["tractor"], "quantity": 3, "unit_value": "50000"}
                ],
            },
            {"name": "Long", "term_months": 36, "scope": "", "vertical": industry(), "items": []},
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
            {"average_price": prices["excavator"], "quantity": 1, "unit_value": "107000"},
            {"average_price": prices["tractor"], "quantity": 1, "unit_value": "50000"},
            {"average_price": prices["excavator"], "quantity": 1},  # not typed yet
        ]},
        content_type="application/json",
    )  # fmt: skip
    assert post_preview.status_code == 200, r.json()
    data = r.json()
    assert [i["out_of_curve"] for i in data["items"]] == [False, True, False]
    # Out of the curve: no weight (not in the LO)
    assert [i["weight_percent"] for i in data["items"]] == ["51.69", None, "48.31"]
    assert data["totals"]["lo"] == "207000.00"
    # Not typed: the average price's value counts (shown as such)
    assert [i["position"] for i in data["items"]] == ["slightly_above", "compatible", "compatible"]
    assert (data["items"][2]["unit_value"], data["items"][2]["value_from_price"]) == (
        "100000.00",
        True,
    )
    assert data["items"][2]["line_total"] == "100000.00"


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


def test_without_a_typed_value_the_average_price_counts(
    logged_client, managers, customers, prices, catalog
):
    data = body(managers, customers, prices)
    del data["scenarios"][0]["items"][0]["unit_value"]
    data["scenarios"][0]["items"][1]["unit_value"] = None
    r = post(logged_client, data)
    assert r.status_code == 201, r.json()
    items = r.json()["scenarios"][0]["items"]
    assert [i["unit_value"] for i in items] == ["100000.00", "50000.00"]
    # Stored: a newer average price does not change it
    _new_version(logged_client, catalog, prices["excavator"], "120000.00")
    item = logged_client.get(f"{URL}{r.json()['id']}/").json()["scenarios"][0]["items"][0]
    assert (item["unit_value"], item["value_from_price"]) == ("100000.00", False)


def test_position_follows_the_control_panel(logged_client, managers, customers, prices):
    data = body(managers, customers, prices)
    data["scenarios"][0]["items"][0]["unit_value"] = "92000"  # 8% below
    analysis = post(logged_client, data).json()
    item = analysis["scenarios"][0]["items"][0]
    assert (item["variation_percent"], item["position"]) == ("-8.00", "slightly_below")
    settings = PricingSettings.current()
    settings.below_percent = Decimal("7.5")
    settings.save()
    item = logged_client.get(f"{URL}{analysis['id']}/").json()["scenarios"][0]["items"][0]
    assert item["position"] == "below"


def _age_prices(months):
    """Every average price dated a little over `months` months ago."""
    AveragePrice.objects.update(created_at=timezone.now() - timedelta(days=31 * months + 1))


def test_expired_prices_mark_the_analysis_outdated(logged_client, managers, customers, prices):
    analysis = post(logged_client, body(managers, customers, prices)).json()
    assert analysis["is_outdated"] is False
    assert analysis["scenarios"][0]["items"][0]["expired"] is False
    _age_prices(12)
    data = logged_client.get(f"{URL}{analysis['id']}/").json()
    assert data["is_outdated"] is True
    assert data["scenarios"][0]["has_expired"] is True
    assert data["scenarios"][0]["items"][0]["expired"] is True
    # Still accepted (the default)
    assert post(logged_client, body(managers, customers, prices)).status_code == 201


def test_expired_prices_can_be_refused(logged_client, managers, customers, prices):
    settings = PricingSettings.current()
    settings.accept_expired = False
    settings.validity_months = 6
    settings.save()
    _age_prices(5)
    assert post(logged_client, body(managers, customers, prices)).status_code == 201
    _age_prices(6)
    r = post(logged_client, body(managers, customers, prices))
    assert r.status_code == 400
    assert "6 months" in r.json()["scenarios"]["0"]["items"]["0"]["average_price"][0]


def test_the_vertical_is_required(logged_client, managers, customers, prices):
    data = body(managers, customers, prices)
    del data["scenarios"][0]["vertical"]
    r = post(logged_client, data)
    assert r.status_code == 400
    assert "vertical" in r.json()["scenarios"]["0"]


def test_a_sub_vertical_narrows_the_assets(logged_client, managers, customers, prices, catalog):
    data = body(managers, customers, prices)
    data["scenarios"][0]["sub_vertical"] = catalog["yellow"].pk  # the tractor is in "Farm"
    r = post(logged_client, data)
    assert r.status_code == 400
    assert r.json()["scenarios"]["0"]["items"] == {
        "1": {"average_price": ["This asset is not in the scenario's vertical."]}
    }
    data["scenarios"][0]["items"].pop()
    r = post(logged_client, data)
    assert r.status_code == 201, r.json()
    scenario = r.json()["scenarios"][0]
    assert (scenario["vertical"], scenario["sub_vertical"]) == (industry(), catalog["yellow"].pk)
    assert scenario["scope_label"] == "Industry / Yellow line"


def test_assets_of_another_vertical_are_refused(logged_client, managers, customers, prices):
    other = Vertical.objects.create(name="Healthcare")
    data = body(managers, customers, prices)
    data["scenarios"][0]["vertical"] = other.pk
    r = post(logged_client, data)
    assert r.status_code == 400
    assert set(r.json()["scenarios"]["0"]["items"]) == {"0", "1"}


def test_the_sub_vertical_must_be_of_the_vertical(
    logged_client, managers, customers, prices, catalog
):
    other = Vertical.objects.create(name="Healthcare")
    data = body(managers, customers, prices)
    data["scenarios"][0].update(vertical=other.pk, sub_vertical=catalog["yellow"].pk, items=[])
    r = post(logged_client, data)
    assert r.status_code == 400
    assert "sub_vertical" in r.json()["scenarios"]["0"]


def test_preview_flags_assets_outside_the_vertical(logged_client, prices, catalog):
    r = logged_client.post(
        f"{URL}scenario-preview/",
        {"term_months": 24, "vertical": industry(), "sub_vertical": catalog["yellow"].pk,
         "items": [{"average_price": prices["excavator"], "quantity": 1},
                   {"average_price": prices["tractor"], "quantity": 1}]},
        content_type="application/json",
    )  # fmt: skip
    data = r.json()
    assert [i["out_of_scope"] for i in data["items"]] == [False, True]
    assert data["totals"]["lo"] == "100000.00"


def test_verticals_used_by_scenarios_cannot_be_removed(
    logged_client, managers, customers, prices, catalog
):
    data = body(managers, customers, prices)
    data["scenarios"][0].update(sub_vertical=catalog["yellow"].pk, items=[])
    assert post(logged_client, data).status_code == 201
    Vertical.objects.create(name="Spare")
    spare = Vertical.objects.get(name="Spare")
    assert logged_client.delete(f"/api/catalogs/verticals/{spare.pk}/").status_code == 204
    # Industry: used by the scenario (and by asset classes)
    r = logged_client.delete(f"/api/catalogs/verticals/{industry()}/")
    assert r.status_code == 409


def test_efmv_value_comes_from_the_curve_at_the_term(logged_client, managers, customers, prices):
    data = body(managers, customers, prices)
    data["scenarios"][0]["items"][1]["efmv_value"] = "31500"  # typed for the tractor
    r = post(logged_client, data)
    assert r.status_code == 201, r.json()
    items = r.json()["scenarios"][0]["items"]
    # 24 months: excavator 55,000 (curve), tractor typed (its curve gives 30,000)
    assert [(i["efmv_value"], i["curve_value"], i["efmv_from_curve"]) for i in items] == [
        ("55000.00", "55000.00", True),
        ("31500.00", "30000.00", False),
    ]
    # Not typed: it follows the scenario's term
    data["scenarios"][0]["term_months"] = 18
    r = logged_client.put(f"{URL}{r.json()['id']}/", data, content_type="application/json")
    items = r.json()["scenarios"][0]["items"]
    assert [i["efmv_value"] for i in items] == ["62500.00", "31500.00"]
    # Weighted over the LO: (2 × 62,500 + 31,500) / 250,000
    assert r.json()["scenarios"][0]["totals"]["efmv_percent"] == "62.60"


def test_scenario_preview_with_efmv_values(logged_client, prices):
    r = logged_client.post(
        f"{URL}scenario-preview/",
        {"term_months": 36, "items": [
            {"average_price": prices["excavator"], "quantity": 1, "efmv_value": "0"},
            {"average_price": prices["tractor"], "quantity": 1},  # its curve stops at 24
        ]},
        content_type="application/json",
    )  # fmt: skip
    assert r.status_code == 200, r.json()
    items = r.json()["items"]
    assert [(i["efmv_value"], i["curve_value"]) for i in items] == [
        ("0.00", "42500.00"),
        (None, None),
    ]
    r = logged_client.post(
        f"{URL}scenario-preview/",
        {"term_months": 12, "items": [
            {"average_price": prices["excavator"], "quantity": 1, "efmv_value": "-1"},
        ]},
        content_type="application/json",
    )  # fmt: skip
    assert r.status_code == 400
