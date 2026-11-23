import pytest
from django.utils import timezone

from .models import AveragePrice, PricePoint
from .testing import TEMPLATE, URL, _new_version, _payload, _post

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
            "percent": "70.00000",
        },
        {
            "term_months": 24,
            "mode": "value",
            "amount": "55000.0000",
            "value": "55000.00",
            "percent": "55.00000",
        },
        {
            "term_months": 36,
            "mode": "percent",
            "amount": "42.5000",
            "value": "42500.00",
            "percent": "42.50000",
        },
    ]
    # Specs are stored with the template as it was
    assert data["specs"] == [{**TEMPLATE[0], "value": "2500"}, {**TEMPLATE[1], "value": "Steel"}]
    assert data["increasing_terms"] == []


def test_monthly_curve_in_detail(logged_client, price):
    curve = logged_client.get(f"{URL}{price.pk}/").json()["curve"]
    assert len(curve) == 37  # months 0..36
    assert curve[0] == {"month": 0, "value": "100000.00", "percent": "100.00000", "is_anchor": True}
    # month 13 = 70000 + (55000 - 70000) / 12 * 1
    assert curve[13] == {
        "month": 13,
        "value": "68750.00",
        "percent": "68.75000",
        "is_anchor": False,
    }
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


@pytest.mark.parametrize("description", ["", "   ", None])
def test_description_is_optional(logged_client, catalog, description):
    payload = _payload(catalog)
    if description is None:
        del payload["description"]
    else:
        payload["description"] = description
    r = _post(logged_client, payload)
    assert r.status_code == 201, r.json()
    assert AveragePrice.objects.get(pk=r.json()["id"]).description == ""


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
        history = logged_client.get(f"{URL}{row_id}/history/").json()["versions"]
        assert [h["original_value"] for h in history] == ["120000.00", "110000.00", "100000.00"]
        assert [h["is_current"] for h in history] == [True, False, False]


def test_only_the_current_version_gets_a_new_version(logged_client, catalog, price):
    assert _post(logged_client, _payload(catalog, supersedes=price.pk)).status_code == 201
    r = _post(logged_client, _payload(catalog, supersedes=price.pk))  # price is old now
    assert r.status_code == 400
    assert "supersedes" in r.json()


# --- Delete -------------------------------------------------------------------------------


def _history(client, row_id):
    return client.get(f"{URL}{row_id}/history/").json()


def _versions(client, row_id):
    return [(h["original_value"], h["is_current"]) for h in _history(client, row_id)["versions"]]


def test_deleting_the_only_version_erases_the_row(logged_client, price):
    assert logged_client.delete(f"{URL}{price.pk}/").status_code == 204
    assert not AveragePrice.objects.filter(pk=price.pk).exists()
    assert PricePoint.objects.count() == 0
    assert logged_client.get(URL).json()["count"] == 0


def test_deleting_the_current_version_makes_the_newest_left_current(logged_client, catalog, price):
    second = _new_version(logged_client, catalog, price.pk, "110000")
    third = _new_version(logged_client, catalog, second, "120000")
    assert logged_client.delete(f"{URL}{third}/").status_code == 204
    assert not AveragePrice.objects.filter(pk=third).exists()
    assert _versions(logged_client, price.pk) == [("110000.00", True), ("100000.00", False)]
    assert [r["id"] for r in logged_client.get(URL).json()["results"]] == [second]


def test_deleting_a_middle_version_relinks_the_others(logged_client, catalog, price):
    second = _new_version(logged_client, catalog, price.pk, "110000")
    third = _new_version(logged_client, catalog, second, "120000")
    assert logged_client.delete(f"{URL}{second}/").status_code == 204
    assert AveragePrice.objects.get(pk=third).supersedes_id == price.pk
    for row_id in (price.pk, third):
        assert _versions(logged_client, row_id) == [("120000.00", True), ("100000.00", False)]


def test_deleting_the_oldest_version(logged_client, catalog, price):
    second = _new_version(logged_client, catalog, price.pk, "110000")
    assert logged_client.delete(f"{URL}{price.pk}/").status_code == 204
    assert AveragePrice.objects.get(pk=second).supersedes_id is None
    assert _versions(logged_client, second) == [("110000.00", True)]


def test_new_version_after_deleting_the_newest(logged_client, catalog, price):
    second = _new_version(logged_client, catalog, price.pk, "110000")
    logged_client.delete(f"{URL}{second}/")  # price is current again
    third = _new_version(logged_client, catalog, price.pk, "130000")
    assert _versions(logged_client, third) == [("130000.00", True), ("100000.00", False)]


def test_delete_all_versions_hides_them(logged_client, catalog, price, user):
    second = _new_version(logged_client, catalog, price.pk, "110000")
    assert logged_client.delete(f"{URL}{second}/history/").status_code == 204
    assert logged_client.get(URL).json()["count"] == 0
    rows = AveragePrice.objects.filter(pk__in=[price.pk, second])
    assert all(r.deleted_at and r.deleted_by == user and not r.is_current for r in rows)
    assert logged_client.delete(f"{URL}{price.pk}/history/").status_code == 409
    # Hidden rows cannot get new versions
    assert _post(logged_client, _payload(catalog, supersedes=second)).status_code == 400


def test_hidden_versions_leave_the_history_of_a_listed_row(logged_client, catalog, price, user):
    # Left by the former per-version delete, which only hid the version
    second = _new_version(logged_client, catalog, price.pk, "110000")
    AveragePrice.objects.filter(pk=price.pk).update(deleted_at=timezone.now(), deleted_by=user)
    history = _history(logged_client, second)
    assert _versions(logged_client, second) == [("110000.00", True)]
    assert history["average"]["count"] == 1


# --- Average of the versions ----------------------------------------------------------------


def test_history_average(logged_client, catalog, price):
    # price: 100,000; 12 m = 70% (70,000); 24 m = 55,000 (55%) — see _payload
    second = _new_version(logged_client, catalog, price.pk, "120000")
    average = _history(logged_client, second)["average"]
    assert average["count"] == 2
    assert average["original_value"] == "110000.00"
    first_12 = price.points.get(term_months=12)
    second_points = {p.term_months: p for p in AveragePrice.objects.get(pk=second).points.all()}
    expected_12 = (first_12.value + second_points[12].value) / 2
    assert average["points"][0]["term_months"] == 12
    assert average["points"][0]["value"] == f"{expected_12:.2f}"
    assert average["points"][0]["count"] == 2


def test_history_average_of_a_single_version(logged_client, price):
    average = _history(logged_client, price.pk)["average"]
    assert average["count"] == 1
    assert average["original_value"] == "100000.00"


# --- Specification suggestions --------------------------------------------------------------

SUGGESTIONS = f"{URL}spec-suggestions/"


def test_spec_suggestions(logged_client, catalog):
    for hours in ("2500", "2500", "1800"):
        assert _post(logged_client, _payload(catalog, specs={"hours": hours})).status_code == 201
    excavators = catalog["excavators"].pk
    r = logged_client.get(SUGGESTIONS, {"asset_class": excavators, "key": "hours"})
    assert r.json() == ["2500", "1800"]  # most used first
    r = logged_client.get(SUGGESTIONS, {"asset_class": excavators, "key": "hours", "search": "18"})
    assert r.json() == ["1800"]
    # Other asset classes and unknown keys: nothing
    r = logged_client.get(SUGGESTIONS, {"asset_class": excavators, "key": "nope"})
    assert r.json() == []


def test_spec_suggestions_skip_hidden_prices(logged_client, catalog, price):
    logged_client.delete(f"{URL}{price.pk}/history/")
    r = logged_client.get(SUGGESTIONS, {"asset_class": catalog["excavators"].pk, "key": "hours"})
    assert r.json() == []


def test_spec_suggestions_need_asset_class_and_key(logged_client):
    assert logged_client.get(SUGGESTIONS, {"key": "hours"}).status_code == 400
    assert logged_client.get(SUGGESTIONS, {"asset_class": "1"}).status_code == 400


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
    # Even when the price was deleted from the list (hidden, kept in the database)
    logged_client.delete(f"{URL}{price.pk}/history/")
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
        {"term_months": 12, "value": "70000.00", "percent": "70.00000"},
        {"term_months": 24, "value": "72000.00", "percent": "72.00000"},
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


# --- Column filters ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"model": "320"}, ["320 GC"]),
        ({"model": "deere"}, ["210 G"]),  # the manufacturer counts too
        ({"model": "  GC  "}, ["320 GC"]),
        ({"original_value_min": "95000"}, ["320 GC"]),
        ({"original_value_max": "90000.00"}, ["210 G"]),
        ({"original_value_min": "80000", "original_value_max": "95000"}, ["210 G"]),
        ({"original_value_min": "abc"}, ["210 G", "320 GC"]),  # ignored
        ({"created_from": "2000-01-01"}, ["210 G", "320 GC"]),
        ({"created_to": "2000-01-01"}, []),
        ({"created_from": "not-a-date"}, ["210 G", "320 GC"]),  # ignored
    ],
)
def test_list_column_filters(logged_client, rows, params, expected):
    results = logged_client.get(URL, {**params, "ordering": "model"}).json()["results"]
    assert [r["model"] for r in results] == expected


def test_list_created_filter_includes_the_whole_day(logged_client, rows):
    today = timezone.localdate().isoformat()
    params = {"created_from": today, "created_to": today}
    assert logged_client.get(URL, params).json()["count"] == 2


def test_created_by_follows_the_user_name_setting(logged_client, price):
    from system.models import SystemSettings

    assert logged_client.get(f"{URL}{price.pk}/").json()["created_by_name"] == "Ana Souza"
    SystemSettings.objects.update_or_create(
        pk=1, defaults={"user_name_display": "full_name", "full_name_order": "last_first"}
    )
    assert logged_client.get(URL).json()["results"][0]["created_by_name"] == "Souza, Ana"


def test_keywords(logged_client, catalog):
    r = _post(logged_client, _payload(catalog, keywords=["Usada", " USADA", "Leilão"]))
    assert r.status_code == 201, r.json()
    assert r.json()["keywords"] == ["usada", "leilão"]
    found = logged_client.get(URL, {"search": "leil"}).json()["results"]
    assert [p["id"] for p in found] == [r.json()["id"]]
    # Not given: none
    assert _post(logged_client, _payload(catalog, model="336")).json()["keywords"] == []
