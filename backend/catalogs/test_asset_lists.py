"""Manufacturers and asset classes (catalogs used by the asset lists)."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from .models import AssetClass, Manufacturer, SubVertical, Vertical
from .ratings import average_stars, is_half_star

MANUFACTURERS = "/api/catalogs/manufacturers/"
ASSET_CLASSES = "/api/catalogs/asset-classes/"


@pytest.fixture
def logged_client(client, db):
    user = get_user_model().objects.create_user("tester", password="strong-password-123")
    client.force_login(user)
    return client


def _vertical(name, **fields):
    vertical = Vertical.objects.create(name=name, **fields)
    SubVertical.objects.create(vertical=vertical, **SubVertical.general_defaults())
    return vertical


@pytest.fixture
def verticals(db):
    return {
        "industry": _vertical("Industry"),
        "agro": _vertical("Agribusiness"),
        "mining": _vertical("Mining", is_enabled=False),
    }


def _manufacturer(name, reputation, product_quality, after_sales, **fields):
    return Manufacturer.objects.create(
        name=name,
        reputation=Decimal(reputation),
        product_quality=Decimal(product_quality),
        after_sales=Decimal(after_sales),
        **fields,
    )


@pytest.fixture
def manufacturers(db):
    return [
        _manufacturer("John Deere", "5", "4.5", "4"),  # average 4.50
        _manufacturer("Caterpillar", "4.5", "5", "3.5"),  # average 4.33
        _manufacturer("Acme", "1", "2", "0", is_enabled=False),  # average 1.00
    ]


@pytest.fixture
def subs(verticals):
    """General sub-verticals of each vertical, plus Industry / Yellow line."""
    general = {k: v.sub_verticals.get(is_general=True) for k, v in verticals.items()}
    yellow = SubVertical.objects.create(
        vertical=verticals["industry"],
        name="Yellow line",
        risk="high",
        allowed_terms=[24, 36],
        recommended_term=24,
    )
    return {**general, "yellow": yellow}


STARS = {
    "liquidity": "4.5",
    "value_retention": "4",
    "technology_renewal": "1",
    "usage_breadth": "3.5",
}


def _asset_class(name, sub_vertical, **fields):
    return AssetClass.objects.create(
        name=name,
        sub_vertical=sub_vertical,
        **{**{k: Decimal(v) for k, v in STARS.items()}, **fields},
    )


@pytest.fixture
def asset_classes(subs):
    return [
        _asset_class("Excavators", subs["yellow"], icon="mdi-excavator"),
        _asset_class("Forklifts", subs["industry"], icon="mdi-forklift", liquidity=Decimal("2")),
        _asset_class("Tractors", subs["agro"], icon="mdi-tractor"),
        _asset_class("Drills", subs["mining"], is_enabled=False),
    ]


def _post(client, url, data):
    return client.post(url, data, content_type="application/json")


def _patch(client, url, pk, data):
    return client.patch(f"{url}{pk}/", data, content_type="application/json")


@pytest.mark.django_db
@pytest.mark.parametrize("url", [MANUFACTURERS, ASSET_CLASSES])
def test_requires_login(client, url):
    assert client.get(url).status_code == 403


# --- Remarketing average (pure function) -----------------------------------------------------


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["3.5", "4", "0", "5"], "3.13"),  # 3.125 rounds half up
        (["5", "4.5", "4"], "4.50"),
        (["4.5", "5", "3.5"], "4.33"),
        (["0", "0", "0"], "0.00"),
        ([], "0.00"),
    ],
)
def test_average_stars(values, expected):
    assert average_stars(Decimal(v) for v in values) == Decimal(expected)


def test_average_counts_missing_ratings_as_zero():
    assert average_stars([Decimal("4"), None]) == Decimal("2.00")


@pytest.mark.parametrize(("value", "ok"), [("0", True), ("2.5", True), ("5", True), ("2.3", False)])
def test_is_half_star(value, ok):
    assert is_half_star(Decimal(value)) is ok


# --- Manufacturers ---------------------------------------------------------------------------

MANUFACTURER_STARS = {"reputation": "4.5", "product_quality": "4", "after_sales": "3"}


def test_manufacturers_list(logged_client, manufacturers):
    results = logged_client.get(MANUFACTURERS).json()["results"]
    assert [m["name"] for m in results] == ["Acme", "Caterpillar", "John Deere"]
    deere = results[2]
    # Ratings and their average travel as decimal strings
    assert {k: deere[k] for k in MANUFACTURER_STARS} == {
        "reputation": "5.0",
        "product_quality": "4.5",
        "after_sales": "4.0",
    }
    assert deere["remarketing_average"] == "4.50"
    assert results[1]["remarketing_average"] == "4.33"
    assert "rating" not in deere


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"search": "deere"}, ["John Deere"]),
        ({"is_enabled": "true"}, ["Caterpillar", "John Deere"]),
        ({"is_enabled": "false"}, ["Acme"]),
        ({"ordering": "-remarketing_score"}, ["John Deere", "Caterpillar", "Acme"]),
        ({"ordering": "-product_quality"}, ["Caterpillar", "John Deere", "Acme"]),
    ],
)
def test_manufacturers_filters(logged_client, manufacturers, params, expected):
    results = logged_client.get(MANUFACTURERS, params).json()["results"]
    assert [m["name"] for m in results] == expected


def test_create_manufacturer(logged_client, db):
    r = _post(logged_client, MANUFACTURERS, {"name": "  New   Holland ", **MANUFACTURER_STARS})
    assert r.status_code == 201, r.json()
    m = Manufacturer.objects.get(pk=r.json()["id"])
    assert (m.name, m.reputation, m.product_quality, m.after_sales, m.is_enabled) == (
        "New Holland",
        Decimal("4.5"),
        Decimal("4"),
        Decimal("3"),
        True,
    )
    assert r.json()["remarketing_average"] == "3.83"


def test_ratings_not_filled_in_are_zero_stars(logged_client, db):
    r = _post(logged_client, MANUFACTURERS, {"name": "Unrated", "reputation": "3"})
    assert r.status_code == 201, r.json()
    assert (r.json()["product_quality"], r.json()["after_sales"]) == ("0.0", "0.0")
    assert r.json()["remarketing_average"] == "1.00"


@pytest.mark.parametrize("stars", ["0", "0.5", "3.5", "5"])
def test_manufacturer_ratings_accept_whole_and_half_stars(logged_client, db, stars):
    r = _post(logged_client, MANUFACTURERS, {"name": "X", "after_sales": stars})
    assert r.status_code == 201, r.json()


@pytest.mark.parametrize("stars", ["-0.5", "5.5", "2.3", "abc", None])
def test_manufacturer_ratings_reject_invalid_stars(logged_client, db, stars):
    r = _post(logged_client, MANUFACTURERS, {"name": "X", "reputation": stars})
    assert r.status_code == 400
    assert "reputation" in r.json()


@pytest.mark.parametrize("name", ["", "  "])
def test_manufacturer_name_is_required(logged_client, db, name):
    r = _post(logged_client, MANUFACTURERS, {"name": name, **MANUFACTURER_STARS})
    assert r.status_code == 400
    assert "name" in r.json()


def test_manufacturer_name_unique_ignoring_case(logged_client, manufacturers):
    r = _post(logged_client, MANUFACTURERS, {"name": "JOHN DEERE"})
    assert r.status_code == 400
    assert r.json()["name"] == ["A manufacturer with this name already exists."]
    # Keeping its own name on update is fine
    deere = manufacturers[0]
    assert _patch(logged_client, MANUFACTURERS, deere.pk, {"name": "john deere"}).status_code == 200


def test_update_and_delete_manufacturer(logged_client, manufacturers):
    acme = manufacturers[2]
    r = _patch(logged_client, MANUFACTURERS, acme.pk, {"after_sales": "2.5", "is_enabled": True})
    assert r.status_code == 200
    assert r.json()["remarketing_average"] == "1.83"
    acme.refresh_from_db()
    assert (acme.after_sales, acme.is_enabled) == (Decimal("2.5"), True)
    assert logged_client.delete(f"{MANUFACTURERS}{acme.pk}/").status_code == 204
    assert not Manufacturer.objects.filter(pk=acme.pk).exists()


# --- Sub-vertical options (pickers) ---------------------------------------------------------


def test_sub_vertical_options(logged_client, subs):
    results = logged_client.get("/api/catalogs/sub-verticals/").json()["results"]
    # By vertical, General first
    assert [r["label"] for r in results] == [
        "Agribusiness / General",
        "Industry / General",
        "Industry / Yellow line",
        "Mining / General",
    ]
    yellow = results[2]
    assert yellow == {
        "id": subs["yellow"].pk,
        "name": "Yellow line",
        "is_general": False,
        "label": "Industry / Yellow line",
        "vertical": {"id": subs["yellow"].vertical_id, "name": "Industry", "is_enabled": True},
        "allowed_terms": [24, 36],
        "recommended_term": 24,
    }


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        (
            {"is_enabled": "true"},
            ["Agribusiness / General", "Industry / General", "Industry / Yellow line"],
        ),
        ({"search": "yellow"}, ["Industry / Yellow line"]),
        ({"search": "industry"}, ["Industry / General", "Industry / Yellow line"]),
    ],
)
def test_sub_vertical_options_filters(logged_client, subs, params, expected):
    results = logged_client.get("/api/catalogs/sub-verticals/", params).json()["results"]
    assert [r["label"] for r in results] == expected


def test_general_label_follows_user_language(logged_client, subs):
    logged_client.patch(
        "/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json"
    )
    results = logged_client.get("/api/catalogs/sub-verticals/", {"search": "agri"}).json()
    assert results["results"][0]["label"] == "Agribusiness / Geral"


def test_sub_vertical_options_are_read_only(logged_client, subs):
    r = _post(logged_client, "/api/catalogs/sub-verticals/", {"name": "X"})
    assert r.status_code == 405


# --- Asset classes ---------------------------------------------------------------------------


def test_asset_classes_list(logged_client, asset_classes, subs):
    results = logged_client.get(ASSET_CLASSES).json()["results"]
    assert [a["name"] for a in results] == ["Drills", "Excavators", "Forklifts", "Tractors"]
    excavators = results[1]
    assert excavators["icon"] == "mdi-excavator"
    assert excavators["sub_vertical"] == subs["yellow"].pk
    assert excavators["sub_vertical_detail"]["label"] == "Industry / Yellow line"
    assert excavators["sub_vertical_detail"]["vertical"]["name"] == "Industry"
    # Ratings travel as decimal strings
    assert {k: excavators[k] for k in STARS} == {
        "liquidity": "4.5",
        "value_retention": "4.0",
        "technology_renewal": "1.0",
        "usage_breadth": "3.5",
    }
    assert "rating" not in excavators and "vertical" not in excavators


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"search": "fork"}, ["Forklifts"]),
        ({"search": "yellow"}, ["Excavators"]),  # by sub-vertical name
        ({"search": "industry"}, ["Excavators", "Forklifts"]),  # by vertical name
        ({"is_enabled": "false"}, ["Drills"]),
        ({"ordering": "liquidity,name"}, ["Forklifts", "Drills", "Excavators", "Tractors"]),
        (
            {"ordering": "sub_vertical__vertical__name,name"},
            ["Tractors", "Excavators", "Forklifts", "Drills"],
        ),
    ],
)
def test_asset_classes_filters(logged_client, asset_classes, params, expected):
    results = logged_client.get(ASSET_CLASSES, params).json()["results"]
    assert [a["name"] for a in results] == expected


def test_asset_classes_filter_by_vertical_or_sub_vertical(
    logged_client, asset_classes, subs, verticals
):
    by_vertical = logged_client.get(ASSET_CLASSES, {"vertical": verticals["industry"].pk}).json()
    assert [a["name"] for a in by_vertical["results"]] == ["Excavators", "Forklifts"]
    by_sub = logged_client.get(ASSET_CLASSES, {"sub_vertical": subs["yellow"].pk}).json()
    assert [a["name"] for a in by_sub["results"]] == ["Excavators"]


def _payload(sub, **overrides):
    return {"name": "Cranes", "icon": "mdi-crane", "sub_vertical": sub.pk, **STARS, **overrides}


def test_create_asset_class(logged_client, subs):
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], name=" Mobile  Cranes "))
    assert r.status_code == 201, r.json()
    a = AssetClass.objects.get(pk=r.json()["id"])
    assert (a.name, a.icon, a.sub_vertical, a.is_enabled) == (
        "Mobile Cranes",
        "mdi-crane",
        subs["yellow"],
        True,
    )
    assert (a.liquidity, a.value_retention, a.technology_renewal, a.usage_breadth) == (
        Decimal("4.5"),
        Decimal("4"),
        Decimal("1"),
        Decimal("3.5"),
    )


def test_icon_defaults_to_a_cube(logged_client, subs):
    data = _payload(subs["yellow"])
    del data["icon"]
    r = _post(logged_client, ASSET_CLASSES, data)
    assert r.status_code == 201
    assert r.json()["icon"] == "mdi-cube-outline"


@pytest.mark.parametrize("stars", ["0", "0.5", "2", "3.5", "5", "5.0"])
def test_ratings_accept_whole_and_half_stars(logged_client, subs, stars):
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], liquidity=stars))
    assert r.status_code == 201, r.json()


@pytest.mark.parametrize("stars", ["-0.5", "5.5", "6", "2.3", "2.25", "abc", None])
def test_ratings_reject_invalid_stars(logged_client, subs, stars):
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], value_retention=stars))
    assert r.status_code == 400
    assert "value_retention" in r.json()


@pytest.mark.parametrize(
    "field", ["liquidity", "value_retention", "technology_renewal", "usage_breadth"]
)
def test_rating_not_filled_in_is_zero_stars(logged_client, subs, field):
    data = _payload(subs["yellow"])
    del data[field]
    r = _post(logged_client, ASSET_CLASSES, data)
    assert r.status_code == 201, r.json()
    assert r.json()[field] == "0.0"


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"sub_vertical": None}, "sub_vertical"),
        ({"sub_vertical": 999999}, "sub_vertical"),
        ({"name": "  "}, "name"),
        ({"icon": "not an icon"}, "icon"),
        ({"icon": "<script>"}, "icon"),
    ],
)
def test_asset_class_validation(logged_client, subs, data, field):
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], **data))
    assert r.status_code == 400
    assert field in r.json()


def test_name_unique_within_the_sub_vertical_only(logged_client, asset_classes, subs):
    # "Excavators" exists in Industry / Yellow line
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], name="EXCAVATORS"))
    assert r.status_code == 400
    assert r.json()["name"] == ["This sub-vertical already has an asset class with this name."]
    # Same name in another sub-vertical of the same vertical is fine
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["industry"], name="Excavators"))
    assert r.status_code == 201


def test_sub_vertical_of_a_disabled_vertical_cannot_be_assigned(logged_client, asset_classes, subs):
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["mining"]))
    assert r.status_code == 400
    assert r.json()["sub_vertical"] == ["This business vertical is disabled."]
    forklifts = asset_classes[1]
    r = _patch(logged_client, ASSET_CLASSES, forklifts.pk, {"sub_vertical": subs["mining"].pk})
    assert r.status_code == 400


def test_keeps_sub_vertical_whose_vertical_was_disabled_later(
    logged_client, asset_classes, verticals
):
    forklifts = asset_classes[1]
    verticals["industry"].is_enabled = False
    verticals["industry"].save()
    r = _patch(
        logged_client,
        ASSET_CLASSES,
        forklifts.pk,
        {"name": "Forklifts", "sub_vertical": forklifts.sub_vertical_id, "liquidity": "3"},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["sub_vertical_detail"]["vertical"]["is_enabled"] is False


def test_asset_class_remarketing_average(logged_client, subs):
    r = _post(
        logged_client,
        ASSET_CLASSES,
        _payload(
            subs["yellow"],
            liquidity="3.5",
            value_retention="4",
            technology_renewal="0",
            usage_breadth="5",
        ),
    )
    assert r.json()["remarketing_average"] == "3.13"


def test_asset_classes_sorted_by_remarketing_average(logged_client, asset_classes):
    # Forklifts has liquidity 2 (average 2.63); the others 3.25
    results = logged_client.get(ASSET_CLASSES, {"ordering": "remarketing_score,name"}).json()
    assert [a["name"] for a in results["results"]][0] == "Forklifts"
    assert results["results"][0]["remarketing_average"] == "2.63"


def test_delete_asset_class(logged_client, asset_classes):
    assert logged_client.delete(f"{ASSET_CLASSES}{asset_classes[0].pk}/").status_code == 204
    assert AssetClass.objects.count() == 3


def test_vertical_with_asset_classes_cannot_be_deleted(logged_client, asset_classes, verticals):
    industry = verticals["industry"]
    r = logged_client.delete(f"/api/catalogs/verticals/{industry.pk}/")
    assert r.status_code == 409
    assert (
        r.json()["detail"]
        == "This vertical is in use (asset classes or eFMV analyses) and cannot be deleted."
    )
    assert Vertical.objects.filter(pk=industry.pk).exists()


def test_sub_vertical_with_asset_classes_cannot_be_removed(logged_client, asset_classes, verticals):
    industry = verticals["industry"]
    general = industry.sub_verticals.get(is_general=True)
    payload = {
        "sub_verticals": [
            {
                "id": general.pk,
                "is_general": True,
                "risk": general.risk,
                "allowed_terms": general.allowed_terms,
                "recommended_term": general.recommended_term,
            }
            # "Yellow line" (with Excavators) left out: it would be removed
        ]
    }
    r = _patch(logged_client, "/api/catalogs/verticals/", industry.pk, payload)
    assert r.status_code == 400
    assert r.json()["sub_verticals"] == [
        'The sub-vertical "Yellow line" is in use (asset classes or eFMV analyses) and cannot '
        "be removed."
    ]
    assert industry.sub_verticals.count() == 2


def test_validation_messages_follow_user_language(logged_client, asset_classes, subs):
    logged_client.patch(
        "/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json"
    )
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], name="Excavators"))
    assert r.json()["name"] == ["Esta sub-vertical já tem uma classe de ativo com este nome."]
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], liquidity="2.3"))
    assert r.json()["liquidity"] == ["Use estrelas inteiras ou meias (ex.: 3,5)."]


# --- Keywords and notes ----------------------------------------------------------------------


def test_keywords_are_normalized(logged_client, subs):
    r = _post(
        logged_client,
        ASSET_CLASSES,
        _payload(
            subs["yellow"],
            keywords=["  Escavadeira ", "ESCAVADEIRA", "linha   amarela", "", "Hidráulica"],
            notes="Includes crawler and wheeled models.",
        ),
    )
    assert r.status_code == 201, r.json()
    assert r.json()["keywords"] == ["escavadeira", "linha amarela", "hidráulica"]
    assert r.json()["notes"] == "Includes crawler and wheeled models."


def test_keywords_and_notes_are_optional(logged_client, subs):
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"]))
    assert r.status_code == 201
    assert (r.json()["keywords"], r.json()["notes"]) == ([], "")


def test_keyword_limits(logged_client, subs):
    too_many = [f"word {i}" for i in range(31)]
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], keywords=too_many))
    assert r.status_code == 400
    assert "keywords" in r.json()
    r = _post(logged_client, ASSET_CLASSES, _payload(subs["yellow"], keywords=["x" * 51]))
    assert r.status_code == 400


def test_search_by_keyword(logged_client, asset_classes):
    excavators = asset_classes[0]
    excavators.keywords = ["escavadeira", "hidráulica"]
    excavators.save()
    for term in ("escavad", "HIDRÁULICA"):
        results = logged_client.get(ASSET_CLASSES, {"search": term}).json()["results"]
        assert [a["name"] for a in results] == ["Excavators"], term


# --- Specification templates (per asset class) ----------------------------------------------


def _template_url(asset_class):
    return f"/api/catalogs/asset-classes/{asset_class.pk}/spec-template/"


def test_spec_template_starts_empty(logged_client, asset_classes):
    assert logged_client.get(_template_url(asset_classes[0])).json() == {"fields": []}


def test_save_spec_template(logged_client, asset_classes):
    excavators = asset_classes[0]
    fields = [
        {"label": "Operating hours", "kind": "number", "unit": "h", "required": True},
        {"label": " Undercarriage ", "kind": "text"},
    ]
    r = logged_client.put(
        _template_url(excavators), {"fields": fields}, content_type="application/json"
    )
    assert r.status_code == 200, r.json()
    assert r.json()["fields"] == [
        {
            "key": "operating_hours",
            "label": "Operating hours",
            "kind": "number",
            "unit": "h",
            "required": True,
            "options": [],
        },
        {
            "key": "undercarriage",
            "label": "Undercarriage",
            "kind": "text",
            "unit": "",
            "required": False,
            "options": [],
        },
    ]
    excavators.refresh_from_db()
    assert len(excavators.spec_template) == 2
    # Returned with the asset class (read-only there)
    listed = logged_client.get(ASSET_CLASSES, {"search": "excavators"}).json()["results"][0]
    assert listed["spec_template"][0]["key"] == "operating_hours"


def test_spec_template_validation(logged_client, asset_classes):
    r = logged_client.put(
        _template_url(asset_classes[0]),
        {"fields": [{"label": "Hours"}, {"label": "hours"}, {"label": "X", "kind": "date"}]},
        content_type="application/json",
    )
    assert r.status_code == 400
    assert set(r.json()["fields"]) == {"1", "2"}


def test_editing_an_asset_class_keeps_its_spec_template(logged_client, asset_classes):
    excavators = asset_classes[0]
    template = [{"key": "h", "label": "H", "kind": "number", "unit": "", "required": False}]
    excavators.spec_template = template
    excavators.save()
    # The template is read-only in the asset class itself
    r = _patch(
        logged_client, ASSET_CLASSES, excavators.pk, {"name": "Excavators", "spec_template": []}
    )
    assert r.status_code == 200, r.json()
    excavators.refresh_from_db()
    assert excavators.spec_template == template


def test_sub_verticals_have_no_spec_template(logged_client, subs):
    option = logged_client.get("/api/catalogs/sub-verticals/").json()["results"][0]
    assert "spec_template" not in option
    r = logged_client.get(f"/api/catalogs/sub-verticals/{subs['yellow'].pk}/spec-template/")
    assert r.status_code == 404


# --- Grid column filters ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"name": "excav"}, ["Excavators"]),
        ({"name": "  EXCAV "}, ["Excavators"]),
        ({"name": "escavadeira"}, ["Excavators"]),  # a keyword
        ({"remarketing_min": "4"}, ["Excavators"]),
        ({"remarketing_min": "1"}, ["Excavators", "Forklifts"]),
        ({"remarketing_min": "abc"}, ["Drills", "Excavators", "Forklifts", "Tractors"]),
        ({"is_enabled": "false"}, ["Drills"]),
    ],
)
def test_asset_class_column_filters(logged_client, asset_classes, params, expected):
    excavators, forklifts, tractors, drills = asset_classes
    excavators.keywords = ["escavadeira"]
    for field in ("liquidity", "value_retention", "technology_renewal", "usage_breadth"):
        setattr(excavators, field, Decimal("4.5"))
        setattr(forklifts, field, Decimal("1.5"))
        setattr(tractors, field, Decimal("0"))
        setattr(drills, field, Decimal("0"))
    for asset_class in asset_classes:
        asset_class.save()
    results = logged_client.get(ASSET_CLASSES, {**params, "ordering": "name"}).json()["results"]
    assert [a["name"] for a in results] == expected


def test_manufacturer_keywords(logged_client, db):
    r = _post(logged_client, MANUFACTURERS, {"name": "Deere", "keywords": [" Agro ", "agro"]})
    assert r.status_code == 201, r.json()
    assert r.json()["keywords"] == ["agro"]
    found = logged_client.get(MANUFACTURERS, {"search": "agr"}).json()["results"]
    assert [m["name"] for m in found] == ["Deere"]
