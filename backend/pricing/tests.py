import pytest
from django.contrib.auth import get_user_model

from catalogs.models import AssetClass, Manufacturer, SubVertical, Vertical

from .models import AveragePrice

URL = "/api/average-prices/"

TEMPLATE = [
    {"key": "hours", "label": "Operating hours", "kind": "number", "unit": "h", "required": True},
    {"key": "tracks", "label": "Undercarriage", "kind": "text", "unit": "", "required": False},
]


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        "tester", password="strong-password-123", first_name="Ana", last_name="Souza"
    )


@pytest.fixture
def logged_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def catalog(db):
    industry = Vertical.objects.create(name="Industry")
    SubVertical.objects.create(vertical=industry, **SubVertical.general_defaults())
    yellow = SubVertical.objects.create(
        vertical=industry,
        name="Yellow line",
        risk="high",
        allowed_terms=[12, 24, 36],
        recommended_term=24,
    )
    excavators = AssetClass.objects.create(
        name="Excavators", sub_vertical=yellow, spec_template=TEMPLATE
    )
    cat = Manufacturer.objects.create(name="Caterpillar")
    deere = Manufacturer.objects.create(name="John Deere")
    return {"yellow": yellow, "excavators": excavators, "cat": cat, "deere": deere}


def _payload(catalog, **overrides):
    return {
        "asset_class": catalog["excavators"].pk,
        "manufacturer": catalog["cat"].pk,
        "model": " 320 GC ",
        "description": "Hydraulic excavator, 20 t class.",
        "specs": {"hours": "2.500".replace(".", ""), "tracks": "Steel"},
        "original_value": "100000.00",
        "points": [
            {"term_months": 12, "mode": "percent", "amount": "70"},
            {"term_months": 24, "mode": "value", "amount": "55000"},
            {"term_months": 36, "mode": "percent", "amount": "42.5"},
        ],
        **overrides,
    }


def _post(client, data):
    return client.post(URL, data, content_type="application/json")


@pytest.fixture
def price(logged_client, catalog):
    r = _post(logged_client, _payload(catalog))
    assert r.status_code == 201, r.json()
    return AveragePrice.objects.get(pk=r.json()["id"])


# --- Create ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_requires_login(client):
    assert client.get(URL).status_code == 403


def test_create(logged_client, catalog):
    r = _post(logged_client, _payload(catalog))
    assert r.status_code == 201, r.json()
    data = r.json()
    assert data["vertical"]["name"] == "Industry"
    assert data["sub_vertical"]["label"] == "Industry / Yellow line"
    assert data["asset_class"]["name"] == "Excavators"
    assert data["manufacturer"]["name"] == "Caterpillar"
    assert data["model"] == "320 GC"
    assert data["currency"] == "BRL"
    assert data["original_value"] == "100000.00"
    assert data["created_by_name"] == "Ana Souza"
    assert data["is_current"] is True
    # Each term keeps how it was entered and its resolved value
    assert data["points"] == [
        {
            "term_months": 12,
            "mode": "percent",
            "amount": "70.0000",
            "value": "70000.00",
            "percent": "70.00",
        },
        {
            "term_months": 24,
            "mode": "value",
            "amount": "55000.0000",
            "value": "55000.00",
            "percent": "55.00",
        },
        {
            "term_months": 36,
            "mode": "percent",
            "amount": "42.5000",
            "value": "42500.00",
            "percent": "42.50",
        },
    ]
    # Specs are stored with the template as it was
    assert data["specs"] == [{**TEMPLATE[0], "value": "2500"}, {**TEMPLATE[1], "value": "Steel"}]
    assert data["increasing_terms"] == []


def test_monthly_curve_in_detail(logged_client, price):
    curve = logged_client.get(f"{URL}{price.pk}/").json()["curve"]
    assert len(curve) == 37  # months 0..36
    assert curve[0] == {"month": 0, "value": "100000.00", "percent": "100.00", "is_anchor": True}
    # month 13 = 70000 + (55000 - 70000) / 12 * 1
    assert curve[13] == {"month": 13, "value": "68750.00", "percent": "68.75", "is_anchor": False}
    assert curve[36]["value"] == "42500.00"


def test_list_shows_no_curve(logged_client, price):
    row = logged_client.get(URL).json()["results"][0]
    assert "curve" not in row


def test_value_higher_than_a_shorter_term_is_only_a_warning(logged_client, catalog):
    data = _payload(
        catalog,
        points=[
            {"term_months": 12, "mode": "percent", "amount": "60"},
            {"term_months": 24, "mode": "percent", "amount": "65"},
            {"term_months": 36, "mode": "percent", "amount": "50"},
        ],
    )
    r = _post(logged_client, data)
    assert r.status_code == 201
    assert r.json()["increasing_terms"] == [24]


@pytest.mark.parametrize(
    "points",
    [
        [{"term_months": 12, "mode": "percent", "amount": "70"}],  # missing terms
        [  # a term that is not allowed
            {"term_months": 12, "mode": "percent", "amount": "70"},
            {"term_months": 24, "mode": "percent", "amount": "60"},
            {"term_months": 48, "mode": "percent", "amount": "50"},
        ],
        [  # repeated term
            {"term_months": 12, "mode": "percent", "amount": "70"},
            {"term_months": 12, "mode": "percent", "amount": "60"},
            {"term_months": 24, "mode": "percent", "amount": "50"},
        ],
    ],
)
def test_terms_must_be_the_sub_vertical_terms(logged_client, catalog, points):
    r = _post(logged_client, _payload(catalog, points=points))
    assert r.status_code == 400
    assert r.json()["points"] == ["Fill in exactly these terms (months): 12, 24, 36."]


@pytest.mark.parametrize(
    ("point", "field"),
    [
        ({"term_months": 12, "mode": "percent", "amount": "1000"}, "amount"),
        ({"term_months": 12, "mode": "percent", "amount": "-1"}, "amount"),
        ({"term_months": 12, "mode": "value", "amount": "100.555"}, "amount"),
        ({"term_months": 12, "mode": "other", "amount": "1"}, "mode"),
    ],
)
def test_point_validation(logged_client, catalog, point, field):
    others = [
        {"term_months": 24, "mode": "percent", "amount": "60"},
        {"term_months": 36, "mode": "percent", "amount": "50"},
    ]
    r = _post(logged_client, _payload(catalog, points=[point, *others]))
    assert r.status_code == 400
    assert field in r.json()["points"]["0"]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"model": "  "}, "model"),
        ({"description": ""}, "description"),
        ({"original_value": "0"}, "original_value"),
        ({"original_value": "-10"}, "original_value"),
        ({"currency": "USD"}, "currency"),  # only BRL for now
        ({"asset_class": 999999}, "asset_class"),
        ({"manufacturer": None}, "manufacturer"),
    ],
)
def test_field_validation(logged_client, catalog, overrides, field):
    r = _post(logged_client, _payload(catalog, **overrides))
    assert r.status_code == 400
    assert field in r.json()


def test_specs_follow_the_asset_class_template(logged_client, catalog):
    r = _post(logged_client, _payload(catalog, specs={"tracks": "Rubber"}))
    assert r.status_code == 400
    assert r.json()["specs"] == {"hours": ["This field is required."]}
    r = _post(logged_client, _payload(catalog, specs={"hours": "a lot"}))
    assert r.json()["specs"] == {"hours": ["Enter a number."]}
    r = _post(logged_client, _payload(catalog, specs={"hours": "10", "color": "Yellow"}))
    assert r.json()["specs"] == {"color": ["This field is not part of the template."]}


@pytest.mark.parametrize("disabled", ["asset_class", "manufacturer", "vertical"])
def test_disabled_catalog_items_cannot_be_used(logged_client, catalog, disabled):
    target = {
        "asset_class": catalog["excavators"],
        "manufacturer": catalog["cat"],
        "vertical": catalog["yellow"].vertical,
    }[disabled]
    target.is_enabled = False
    target.save()
    r = _post(logged_client, _payload(catalog))
    assert r.status_code == 400


def test_snapshot_does_not_change_with_the_catalogs(logged_client, price, catalog):
    yellow = catalog["yellow"]
    yellow.allowed_terms = [12, 24, 36, 48]
    yellow.save()
    catalog["excavators"].spec_template = []
    catalog["excavators"].save()
    data = logged_client.get(f"{URL}{price.pk}/").json()
    assert [p["term_months"] for p in data["points"]] == [12, 24, 36]
    assert data["specs"][0]["label"] == "Operating hours"


# --- Never edited: new versions --------------------------------------------------------------


def test_rows_cannot_be_edited(logged_client, price):
    for method in (logged_client.put, logged_client.patch):
        r = method(f"{URL}{price.pk}/", {"model": "X"}, content_type="application/json")
        assert r.status_code == 405


def test_new_version_supersedes_the_previous(logged_client, catalog, price):
    r = _post(logged_client, _payload(catalog, model="320 GC (2025)", supersedes=price.pk))
    assert r.status_code == 201, r.json()
    new_id = r.json()["id"]
    price.refresh_from_db()
    assert price.is_current is False
    # Only the new version is listed
    assert [row["id"] for row in logged_client.get(URL).json()["results"]] == [new_id]
    # The previous one is still there, with its values
    old = logged_client.get(f"{URL}{price.pk}/").json()
    assert (old["model"], old["is_current"]) == ("320 GC", False)


def test_history_lists_every_version_newest_first(logged_client, catalog, price):
    second = _post(logged_client, _payload(catalog, original_value="110000", supersedes=price.pk))
    third = _post(
        logged_client, _payload(catalog, original_value="120000", supersedes=second.json()["id"])
    )
    for row_id in (price.pk, third.json()["id"]):  # same answer from any version
        history = logged_client.get(f"{URL}{row_id}/history/").json()
        assert [h["original_value"] for h in history] == ["120000.00", "110000.00", "100000.00"]
        assert [h["is_current"] for h in history] == [True, False, False]


def test_only_the_current_version_gets_a_new_version(logged_client, catalog, price):
    assert _post(logged_client, _payload(catalog, supersedes=price.pk)).status_code == 201
    r = _post(logged_client, _payload(catalog, supersedes=price.pk))  # price is old now
    assert r.status_code == 400
    assert "supersedes" in r.json()


# --- Delete keeps history --------------------------------------------------------------------


def test_delete_hides_but_keeps_the_row(logged_client, price, user):
    assert logged_client.delete(f"{URL}{price.pk}/").status_code == 204
    assert logged_client.get(URL).json()["count"] == 0
    price.refresh_from_db()
    assert price.deleted_at is not None
    assert price.deleted_by == user
    assert logged_client.get(f"{URL}{price.pk}/").json()["deleted_at"] is not None


def test_deleted_or_old_versions_cannot_be_deleted_or_versioned(logged_client, catalog, price):
    logged_client.delete(f"{URL}{price.pk}/")
    assert logged_client.delete(f"{URL}{price.pk}/").status_code == 409
    assert _post(logged_client, _payload(catalog, supersedes=price.pk)).status_code == 400


# --- List ------------------------------------------------------------------------------------


@pytest.fixture
def rows(logged_client, catalog):
    _post(logged_client, _payload(catalog, model="320 GC", original_value="100000"))
    _post(
        logged_client,
        _payload(catalog, model="210 G", manufacturer=catalog["deere"].pk, original_value="90000"),
    )


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"search": "deere"}, ["210 G"]),
        ({"search": "excavators"}, ["210 G", "320 GC"]),
        ({"ordering": "original_value"}, ["210 G", "320 GC"]),
        ({"ordering": "-original_value"}, ["320 GC", "210 G"]),
    ],
)
def test_list_search_and_ordering(logged_client, rows, params, expected):
    results = logged_client.get(URL, params).json()["results"]
    assert [r["model"] for r in results] == expected


def test_list_filters(logged_client, rows, catalog):
    by_manufacturer = logged_client.get(URL, {"manufacturer": catalog["deere"].pk}).json()
    assert [r["model"] for r in by_manufacturer["results"]] == ["210 G"]
    by_sub = logged_client.get(URL, {"sub_vertical": catalog["yellow"].pk}).json()
    assert by_sub["count"] == 2


# --- Catalog items in use cannot be deleted --------------------------------------------------


def test_asset_class_and_manufacturer_in_use_cannot_be_deleted(logged_client, price, catalog):
    r = logged_client.delete(f"/api/catalogs/asset-classes/{catalog['excavators'].pk}/")
    assert r.status_code == 409
    assert r.json()["detail"] == "This asset class is used in average prices and cannot be deleted."
    r = logged_client.delete(f"/api/catalogs/manufacturers/{catalog['cat'].pk}/")
    assert r.status_code == 409
    # Even when the price was deleted (it stays as history)
    logged_client.delete(f"{URL}{price.pk}/")
    assert (
        logged_client.delete(f"/api/catalogs/manufacturers/{catalog['cat'].pk}/").status_code == 409
    )
    # Unused ones can be deleted
    assert (
        logged_client.delete(f"/api/catalogs/manufacturers/{catalog['deere'].pk}/").status_code
        == 204
    )


def test_messages_follow_user_language(logged_client, catalog):
    logged_client.patch(
        "/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json"
    )
    r = _post(logged_client, _payload(catalog, points=[]))
    assert r.json()["points"] == ["Preencha exatamente estes prazos (meses): 12, 24, 36."]


# --- Preview (the form never computes prices itself) -----------------------------------------


def test_preview_resolves_values_curve_and_warnings(logged_client, db):
    r = logged_client.post(
        f"{URL}preview/",
        {
            "original_value": "100000",
            "points": [
                {"term_months": 24, "mode": "value", "amount": "72000"},
                {"term_months": 12, "mode": "percent", "amount": "70"},
            ],
        },
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    data = r.json()
    assert data["points"] == [
        {"term_months": 12, "value": "70000.00", "percent": "70.00"},
        {"term_months": 24, "value": "72000.00", "percent": "72.00"},
    ]
    assert data["increasing_terms"] == [24]
    assert len(data["curve"]) == 25
    assert data["curve"][13]["value"] == "70166.67"
    assert AveragePrice.objects.count() == 0  # nothing saved


@pytest.mark.parametrize(
    "payload",
    [
        {"original_value": "0", "points": [{"term_months": 12, "mode": "value", "amount": "1"}]},
        {"original_value": "100", "points": []},
        {
            "original_value": "100",
            "points": [
                {"term_months": 12, "mode": "value", "amount": "1"},
                {"term_months": 12, "mode": "value", "amount": "2"},
            ],
        },
    ],
)
def test_preview_validation(logged_client, db, payload):
    r = logged_client.post(f"{URL}preview/", payload, content_type="application/json")
    assert r.status_code == 400
