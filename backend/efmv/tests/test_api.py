from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import UserPreferences
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
def managers(catalog):
    """Ana and Bruno, account managers who work in Industry (the vertical of the prices)."""
    industry = catalog["yellow"].vertical
    return {
        "ana": make_account_manager("Ana", "Lima", "ana@example.com", [industry]),
        "bruno": make_account_manager("Bruno", "Reis", "bruno@example.com", [industry]),
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
        "vertical": industry(),
        "scenarios": [
            {
                "name": "Base",
                "term_months": 24,
                "scope": "Yellow line fleet",
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
    # Official name: term + name
    assert scenario["title"] == "24 Months - Base"
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
                "items": [
                    {"average_price": prices["tractor"], "quantity": 3, "unit_value": "50000"}
                ],
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
    assert rows[1]["scenario_names"] == ["24 Months - Base"]
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
    del data["vertical"]
    r = post(logged_client, data)
    assert r.status_code == 400
    assert "vertical" in r.json()


def test_a_sub_vertical_narrows_the_assets(logged_client, managers, customers, prices, catalog):
    data = body(managers, customers, prices, sub_vertical=catalog["yellow"].pk)
    r = post(logged_client, data)  # the tractor is in "Farm"
    assert r.status_code == 400
    assert r.json()["scenarios"]["0"]["items"] == {
        "1": {"average_price": ["This asset is not in the analysis's vertical."]}
    }
    data["scenarios"][0]["items"].pop()
    r = post(logged_client, data)
    assert r.status_code == 201, r.json()
    analysis = r.json()
    assert (analysis["vertical"], analysis["sub_vertical"]) == (industry(), catalog["yellow"].pk)
    assert analysis["vertical_label"] == "Industry / Yellow line"


def test_assets_of_another_vertical_are_refused(logged_client, managers, customers, prices):
    other = Vertical.objects.create(name="Healthcare")
    managers["ana"].profile.verticals.add(other)
    r = post(logged_client, body(managers, customers, prices, vertical=other.pk))
    assert r.status_code == 400
    assert set(r.json()["scenarios"]["0"]["items"]) == {"0", "1"}


def test_the_sub_vertical_must_be_of_the_vertical(
    logged_client, managers, customers, prices, catalog
):
    other = Vertical.objects.create(name="Healthcare")
    managers["ana"].profile.verticals.add(other)
    data = body(managers, customers, prices, vertical=other.pk, sub_vertical=catalog["yellow"].pk)
    data["scenarios"][0]["items"] = []
    r = post(logged_client, data)
    assert r.status_code == 400
    assert "sub_vertical" in r.json()


def test_the_premises_cannot_change(logged_client, managers, customers, prices):
    analysis = post(logged_client, body(managers, customers, prices)).json()
    url = f"{URL}{analysis['id']}/"
    other = Vertical.objects.create(name="Healthcare")
    r = logged_client.patch(url, {"vertical": other.pk}, content_type="application/json")
    assert r.status_code == 400 and "vertical" in r.json()
    r = logged_client.patch(
        url, {"customer": customers["beta"].pk}, content_type="application/json"
    )
    assert r.status_code == 400 and "customer" in r.json()
    # The scenarios alone are changed freely (the premises are not sent)
    scenarios = body(managers, customers, prices)["scenarios"]
    scenarios[0]["term_months"] = 12
    r = logged_client.patch(url, {"scenarios": scenarios}, content_type="application/json")
    assert r.status_code == 200, r.json()
    assert r.json()["scenarios"][0]["term_months"] == 12
    assert r.json()["vertical"] == industry()


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


def test_account_manager_summary(logged_client, managers, customers, prices, catalog):
    # Ana: 2 analyses in Industry, 1 more in Healthcare; primary manager of Acme only
    for _ in range(2):
        assert post(logged_client, body(managers, customers, prices)).status_code == 201
    healthcare = Vertical.objects.create(name="Healthcare")
    managers["ana"].profile.verticals.add(healthcare)
    data = body(managers, customers, prices, vertical=healthcare.pk)
    data["scenarios"][0]["items"] = []
    assert post(logged_client, data).status_code == 201
    r = logged_client.get(f"{URL}account-manager-summary/", {"account_manager": managers["ana"].pk})
    assert r.status_code == 200, r.json()
    summary = r.json()
    assert summary["full_name"] == "Ana Lima"
    assert summary["analyses_count"] == 3
    assert summary["top_verticals"] == [
        {"id": industry(), "name": "Industry", "analyses": 2},
        {"id": healthcare.pk, "name": "Healthcare", "analyses": 1},
    ]
    assert summary["primary_customers_count"] == 1
    # Bruno: no analyses yet; primary manager of Beta
    r = logged_client.get(
        f"{URL}account-manager-summary/", {"account_manager": managers["bruno"].pk}
    )
    assert (r.json()["analyses_count"], r.json()["top_verticals"]) == (0, [])
    assert r.json()["primary_customers_count"] == 1
    assert logged_client.get(f"{URL}account-manager-summary/").status_code == 400


def test_verticals_used_by_scenarios_cannot_be_removed(
    logged_client, managers, customers, prices, catalog
):
    data = body(managers, customers, prices, sub_vertical=catalog["yellow"].pk)
    data["scenarios"][0]["items"] = []
    assert post(logged_client, data).status_code == 201
    Vertical.objects.create(name="Spare")
    spare = Vertical.objects.get(name="Spare")
    assert logged_client.delete(f"/api/catalogs/verticals/{spare.pk}/").status_code == 204
    # Industry: used by the analysis (and by asset classes)
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
    # Negative: a disposal cost
    assert r.status_code == 200, r.json()
    assert r.json()["items"][0]["efmv_value"] == "-1.00"


def test_scenario_title_is_term_and_name(logged_client, managers, customers, prices):
    base = {"term_months": 36, "items": []}
    scenarios = [
        {**base, "name": " Desktops "},
        {**base, "name": ""},  # the name may be empty
        {**base, "term_months": 1},
        {**base, "term_months": 60, "name": "Desktops"},  # same name, another term
    ]
    r = post(logged_client, body(managers, customers, prices, scenarios=scenarios))
    assert r.status_code == 201, r.json()
    # In the order of their official names: term (as a number), then name
    assert [s["title"] for s in r.json()["scenarios"]] == [
        "1 Month",
        "36 Months",
        "36 Months - Desktops",
        "60 Months - Desktops",
    ]
    # Same term and no name twice: the same official name
    r = post(logged_client, body(managers, customers, prices, scenarios=[base, base]))
    assert r.status_code == 400
    assert "name" in r.json()["scenarios"]["1"]


def test_scenario_title_in_the_user_language(logged_client, user, managers, customers, prices):
    preferences = UserPreferences.for_user(user)
    preferences.language = "pt-br"
    preferences.save()
    scenario = {"name": "Desktops", "term_months": 36, "items": []}
    r = post(logged_client, body(managers, customers, prices, scenarios=[scenario]))
    assert r.json()["scenarios"][0]["title"] == "36 Meses - Desktops"


def test_efmv_typed_as_a_percentage_of_the_unit_value(logged_client, managers, customers, prices):
    items = [
        {
            "average_price": prices["excavator"],
            "quantity": 1,
            "unit_value": "100",
            "efmv_percent": "25",
        },
        # Unit value not typed: a percentage of the average price's value (50,000)
        {"average_price": prices["tractor"], "quantity": 1, "efmv_percent": "12.5"},
    ]
    r = logged_client.post(
        f"{URL}scenario-preview/",
        {"term_months": 24, "items": items},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    assert [(i["efmv_value"], i["efmv_from_curve"]) for i in r.json()["items"]] == [
        ("25.00", False),
        ("6250.00", False),
    ]
    # Shown below the field: the eFMV as a % of the unit value
    assert [i["efmv_percent"] for i in r.json()["items"]] == ["25.00", "12.50"]
    # Saved as the value it gives
    data = body(managers, customers, prices)
    data["scenarios"][0]["items"] = items
    r = post(logged_client, data)
    assert r.status_code == 201, r.json()
    assert [i["efmv_value"] for i in r.json()["scenarios"][0]["items"]] == ["25.00", "6250.00"]
    # Negative: a disposal cost, as a value or as a percentage
    negative = [
        {
            "average_price": prices["excavator"],
            "quantity": 2,
            "unit_value": "100",
            "efmv_value": "-10",
        },
        {
            "average_price": prices["tractor"],
            "quantity": 1,
            "unit_value": "100",
            "efmv_percent": "-5",
        },
    ]
    r = logged_client.post(
        f"{URL}scenario-preview/",
        {"term_months": 24, "items": negative},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    assert [(i["efmv_value"], i["efmv_percent"]) for i in r.json()["items"]] == [
        ("-10.00", "-10.00"),
        ("-5.00", "-5.00"),
    ]
    # (2 × -10 + -5) / 300
    assert r.json()["totals"]["efmv_percent"] == "-8.33"
    data["scenarios"][0]["items"] = negative
    r = post(logged_client, data)
    assert r.status_code == 201, r.json()
    assert [i["efmv_value"] for i in r.json()["scenarios"][0]["items"]] == ["-10.00", "-5.00"]
    # Not both
    items[0]["efmv_value"] = "30"
    r = logged_client.post(
        f"{URL}scenario-preview/",
        {"term_months": 24, "items": items},
        content_type="application/json",
    )
    assert r.status_code == 400


def test_the_vertical_must_be_one_the_account_manager_works_in(
    logged_client, managers, customers, prices
):
    other = Vertical.objects.create(name="Healthcare")
    data = body(managers, customers, prices, vertical=other.pk)
    data["scenarios"][0]["items"] = []
    r = post(logged_client, data)
    assert r.status_code == 400
    assert r.json()["vertical"] == ["This account manager does not work in this vertical."]
    summary = logged_client.get(
        f"{URL}account-manager-summary/", {"account_manager": managers["ana"].pk}
    ).json()
    assert summary["verticals"] == [{"id": industry(), "name": "Industry"}]


def _preview(client, items, term=24):
    r = client.post(
        f"{URL}scenario-preview/",
        {"term_months": term, "items": items},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    return r.json()


def test_a_service_added_to_an_asset(logged_client, prices):
    # 2 excavators at 100,000 (curve at 24 months: 55,000) with a warranty of 5,000 each
    data = _preview(logged_client, [{
        "average_price": prices["excavator"], "quantity": 2, "unit_value": "100000",
        "service": {"name": "Warranty", "value": "5000", "mode": "add"},
    }])  # fmt: skip
    item = data["items"][0]
    assert (item["net_unit_value"], item["line_total"]) == ("100000.00", "200000.00")
    assert item["service"] == {
        "name": "Warranty",
        "mode": "add",
        "value": "5000.00",
        "line_total": "10000.00",
        "weight_percent": "4.76",
        "too_high": False,
    }
    totals = data["totals"]
    assert totals["lo"] == "210000.00"
    assert (totals["hw_percent"], totals["sv_percent"]) == ("95.24", "4.76")
    # 110,000 left at the end of 210,000: lower than 55% without the service
    assert totals["efmv_percent"] == "52.38"


def test_a_service_deducted_from_the_asset(logged_client, prices):
    # Typed 107,000 with 7% of it as a service inside: the asset itself is worth 99,510
    data = _preview(logged_client, [{
        "average_price": prices["excavator"], "quantity": 1, "unit_value": "107000",
        "service": {"name": "Warranty", "percent": "7", "mode": "deduct"},
    }])  # fmt: skip
    item = data["items"][0]
    assert (item["unit_value"], item["net_unit_value"]) == ("107000.00", "99510.00")
    assert item["service"]["value"] == "7490.00"
    # Positioned (and its eFMV %) by what the asset is worth without the service
    assert (item["variation_percent"], item["position"]) == ("-0.49", "compatible")
    assert item["efmv_percent"] == "55.27"
    # The LO is what was typed: the service only moves from HW to SV
    assert data["totals"]["lo"] == "107000.00"
    assert data["totals"]["sv_percent"] == "7.00"


def test_a_service_cannot_be_worth_more_than_the_asset(logged_client, prices):
    data = _preview(logged_client, [{
        "average_price": prices["excavator"], "quantity": 1, "unit_value": "1000",
        "service": {"name": "Warranty", "value": "1500", "mode": "add"},
    }])  # fmt: skip
    assert data["items"][0]["service"]["too_high"] is True
    assert data["totals"]["lo"] == "0.00"


def test_a_deducted_service_cannot_take_the_whole_asset(logged_client, managers, customers, prices):
    service = {"name": "Warranty", "value": "100000", "mode": "deduct"}
    data = _preview(logged_client, [{
        "average_price": prices["excavator"], "quantity": 1, "unit_value": "100000",
        "service": service,
    }])  # fmt: skip
    assert data["items"][0]["service"]["too_high"] is True
    assert data["totals"]["lo"] == "0.00"
    body_ = body(managers, customers, prices)
    body_["scenarios"][0]["items"][0]["service"] = service
    r = post(logged_client, body_)
    assert r.status_code == 400
    assert "service" in r.json()["scenarios"]["0"]["items"]["0"]


def test_services_are_saved_with_their_items(logged_client, managers, customers, prices):
    data = body(managers, customers, prices)
    data["scenarios"][0]["items"][0]["service"] = {
        "name": " Warranty  plus ",
        "percent": "10",
        "mode": "deduct",
    }
    data["scenarios"][0]["items"][1]["service"] = {"name": "Services", "value": "0"}
    r = post(logged_client, data)
    assert r.status_code == 201, r.json()
    analysis = logged_client.get(f"{URL}{r.json()['id']}/").json()
    first, second = analysis["scenarios"][0]["items"]
    # Stored as the value it gave
    assert (first["service"]["name"], first["service"]["value"]) == ("Warranty plus", "10000.00")
    assert (first["service"]["mode"], first["net_unit_value"]) == ("deduct", "90000.00")
    assert (second["service"]["value"], second["service"]["mode"]) == ("0.00", "add")
    # Removing a service: the asset is worth what was typed again
    data["scenarios"][0]["items"][0]["service"] = None
    r = logged_client.patch(
        f"{URL}{r.json()['id']}/", {"scenarios": data["scenarios"]}, content_type="application/json"
    )
    item = r.json()["scenarios"][0]["items"][0]
    assert (item["service"], item["net_unit_value"]) == (None, "100000.00")


def test_the_list_shows_the_last_update_latest_first(
    logged_client, user, managers, customers, prices
):
    first = post(logged_client, body(managers, customers, prices)).json()
    second = post(logged_client, body(managers, customers, prices)).json()
    rows = logged_client.get(URL).json()["results"]
    assert [r["id"] for r in rows] == [second["id"], first["id"]]
    # Saving the first one brings it to the top, with who saved it
    scenarios = body(managers, customers, prices)["scenarios"]
    r = logged_client.patch(
        f"{URL}{first['id']}/", {"scenarios": scenarios}, content_type="application/json"
    )
    assert r.status_code == 200
    rows = logged_client.get(URL).json()["results"]
    assert [r["id"] for r in rows] == [first["id"], second["id"]]
    assert rows[0]["updated_at"] >= rows[1]["updated_at"]
    assert rows[0]["updated_by_name"]
    assert EfmvAnalysis.objects.get(pk=first["id"]).updated_by == user


def test_the_scope_is_written_from_the_assets(logged_client, user, managers, customers, prices):
    from accounts.models import UserPreferences
    from catalogs.models import AssetClass

    excavators = AssetClass.objects.get(name="Excavators")
    excavators.plural_name = "Excavators"
    excavators.translations = {"pt-br": {"name": "Escavadeira", "plural": "Escavadeiras"}}
    excavators.save()
    items = [
        {"average_price": prices["excavator"], "quantity": 20},
        # 1 of 21 units (4.8%): negligible by default
        {"average_price": prices["tractor"], "quantity": 1},
    ]
    data = _preview(logged_client, items)
    assert data["scope_suggestion"] == "Caterpillar Excavators"
    # The user's threshold
    preferences = UserPreferences.for_user(user)
    preferences.scope_threshold = Decimal("1")
    preferences.save()
    data = _preview(logged_client, items)
    # Tractors: a class without a plural yet → the English rule
    assert data["scope_suggestion"] == "Caterpillar Excavators and John Deere Tractors"
    # In the user's language (Spanish not translated: English)
    preferences.language = "pt-br"
    preferences.save()
    data = _preview(logged_client, items)
    assert data["scope_suggestion"] == "Escavadeiras Caterpillar e Tractors John Deere"
    # Also with the analysis
    analysis = post(logged_client, body(managers, customers, prices)).json()
    assert analysis["scenarios"][0]["scope_suggestion"].startswith("Escavadeiras Caterpillar")


def test_keywords_change_after_creation(logged_client, managers, customers, prices):
    analysis = post(
        logged_client, {**body(managers, customers, prices), "keywords": ["Renewal", "2027"]}
    ).json()
    assert analysis["keywords"] == ["renewal", "2027"]
    r = logged_client.patch(
        f"{URL}{analysis['id']}/", {"keywords": ["Renewal Q3"]}, content_type="application/json"
    )
    assert r.status_code == 200, r.json()
    assert r.json()["keywords"] == ["renewal q3"]
    found = logged_client.get(URL, {"search": "q3"}).json()["results"]
    assert [a["id"] for a in found] == [analysis["id"]]
