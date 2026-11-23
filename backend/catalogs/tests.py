import pytest
from django.contrib.auth import get_user_model

from users.testing import make_account_manager

from .models import SubVertical, Vertical

URL = "/api/catalogs/verticals/"


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


def _general(**overrides):
    return {
        "is_general": True,
        "risk": "medium",
        "allowed_terms": [12, 24, 36],
        "recommended_term": 36,
        **overrides,
    }


def _sub(name, **overrides):
    return {
        "name": name,
        "risk": "high",
        "allowed_terms": [24, 36],
        "recommended_term": 24,
        **overrides,
    }


def _create_vertical(name, sub_verticals=(), managers=(), **fields):
    vertical = Vertical.objects.create(name=name, **fields)
    for manager in managers:
        manager.profile.verticals.add(vertical)
    SubVertical.objects.create(vertical=vertical, **SubVertical.general_defaults())
    for sub in sub_verticals:
        SubVertical.objects.create(vertical=vertical, **sub)
    return vertical


@pytest.fixture
def verticals(managers):
    return {
        "industry": _create_vertical(
            "Industry",
            sub_verticals=[_sub("Yellow line")],
            managers=[managers["bruno"], managers["ana"]],
        ),
        "it": _create_vertical(
            "IT",
            sub_verticals=[_sub("Datacenter", risk="low")],
            managers=[managers["ana"]],
            is_enabled=False,
        ),
        "mining": _create_vertical("Mining", notes="Heavy equipment only."),
    }


def _post(client, data):
    return client.post(URL, data, content_type="application/json")


def _patch(client, pk, data):
    return client.patch(f"{URL}{pk}/", data, content_type="application/json")


def _subs(vertical):
    return [
        (s.display_name, s.is_general, s.risk, s.allowed_terms, s.recommended_term)
        for s in vertical.sub_verticals.all()
    ]


# --- Access, list, search --------------------------------------------------------------------


@pytest.mark.django_db
def test_requires_login(client):
    assert client.get(URL).status_code == 403
    assert client.get(f"{URL}defaults/").status_code == 403


def test_defaults(logged_client):
    assert logged_client.get(f"{URL}defaults/").json() == {
        "risk": "medium",
        "allowed_terms": [12, 24, 36, 48, 60],
        "recommended_term": 36,
        "max_term_months": 360,
    }


def test_list_with_sub_verticals_general_first(logged_client, verticals, managers):
    results = logged_client.get(URL).json()["results"]
    assert [v["name"] for v in results] == ["Industry", "IT", "Mining"]
    industry = results[0]
    assert [m["full_name"] for m in industry["account_managers_detail"]] == [
        "Ana Souza",
        "Bruno Lima",
    ]
    assert industry["sub_verticals"] == [
        {
            "id": industry["sub_verticals"][0]["id"],
            "name": "",
            "is_general": True,
            "risk": "medium",
            "allowed_terms": [12, 24, 36, 48, 60],
            "recommended_term": 36,
        },
        {
            "id": industry["sub_verticals"][1]["id"],
            "name": "Yellow line",
            "is_general": False,
            "risk": "high",
            "allowed_terms": [24, 36],
            "recommended_term": 24,
        },
    ]
    assert [s["is_general"] for s in results[2]["sub_verticals"]] == [True]


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("indus", ["Industry"]),
        ("datacenter", ["IT"]),  # sub-vertical name
        ("ana souza", ["Industry", "IT"]),  # each vertical once
    ],
)
def test_search(logged_client, verticals, term, expected):
    results = logged_client.get(URL, {"search": term}).json()["results"]
    assert [v["name"] for v in results] == expected


# --- Create ----------------------------------------------------------------------------------


def test_create_without_sub_verticals_gets_general_with_defaults(logged_client):
    r = _post(logged_client, {"name": "Health"})
    assert r.status_code == 201, r.json()
    vertical = Vertical.objects.get(pk=r.json()["id"])
    assert vertical.is_enabled is True
    assert _subs(vertical) == [("General", True, "medium", [12, 24, 36, 48, 60], 36)]


def test_account_managers_are_not_set_through_the_vertical(logged_client, verticals, managers):
    # The relation belongs to the account manager: here it is read-only and ignored on write
    r = _post(logged_client, {"name": "Health", "account_managers": [managers["carla"].pk]})
    assert r.status_code == 201
    assert Vertical.objects.get(pk=r.json()["id"]).account_manager_profiles.count() == 0

    industry = verticals["industry"]
    r = _patch(logged_client, industry.pk, {"account_managers": []})
    assert r.status_code == 200
    assert industry.account_manager_profiles.count() == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", ["Industry", "Mining"]), ("false", ["IT"]), ("", ["Industry", "IT", "Mining"])],
)
def test_filter_by_enabled(logged_client, verticals, value, expected):
    results = logged_client.get(URL, {"is_enabled": value}).json()["results"]
    assert [v["name"] for v in results] == expected


def test_create_with_sub_verticals(logged_client):
    r = _post(
        logged_client,
        {
            "name": "  Industry ",
            "sub_verticals": [
                _general(risk="low", allowed_terms=[36, 12, 12, 24], recommended_term=24),
                _sub("  Yellow   line "),
            ],
        },
    )
    assert r.status_code == 201, r.json()
    vertical = Vertical.objects.get(pk=r.json()["id"])
    assert vertical.name == "Industry"
    # Terms are de-duplicated and sorted; names normalized
    assert _subs(vertical) == [
        ("General", True, "low", [12, 24, 36], 24),
        ("Yellow line", False, "high", [24, 36], 24),
    ]


def test_any_number_of_months_is_accepted(logged_client):
    r = _post(
        logged_client,
        {
            "name": "Agro",
            "sub_verticals": [_general(allowed_terms=[18, 30, 42], recommended_term=30)],
        },
    )
    assert r.status_code == 201, r.json()


@pytest.mark.parametrize(
    "sub_verticals",
    [
        [],  # no general
        [_sub("Only")],  # no general
        [_general(), _general()],  # two generals
        [_general(), _sub("Same"), _sub("same")],  # duplicate names (case-insensitive)
    ],
)
def test_sub_vertical_list_rules(logged_client, db, sub_verticals):
    r = _post(logged_client, {"name": "X", "sub_verticals": sub_verticals})
    assert r.status_code == 400
    assert "sub_verticals" in r.json()
    assert Vertical.objects.count() == 0


@pytest.mark.parametrize(
    ("item", "field"),
    [
        (_sub("A", recommended_term=48), "recommended_term"),  # not among allowed terms
        (_sub("A", allowed_terms=[]), "allowed_terms"),
        (_sub("A", allowed_terms=[0, 12]), "allowed_terms"),
        (_sub("A", allowed_terms=[12, 361]), "allowed_terms"),
        (_sub("A", risk="extreme"), "risk"),
        (_sub(""), "name"),
        (_sub("General"), "name"),  # reserved, in any language
        (_sub("geral"), "name"),
        ({"name": "A", "risk": "low"}, "allowed_terms"),
    ],
)
def test_sub_vertical_field_validation(logged_client, db, item, field):
    r = _post(logged_client, {"name": "X", "sub_verticals": [_general(), item]})
    assert r.status_code == 400
    # DRF reports list items by position, only the ones that failed: {"1": {field: [...]}}
    errors = r.json()["sub_verticals"]
    assert list(errors) == ["1"]
    assert field in errors["1"]


def test_vertical_name_must_be_unique_ignoring_case(logged_client, verticals):
    r = _post(logged_client, {"name": "INDUSTRY"})
    assert r.status_code == 400
    assert r.json()["name"] == ["A vertical with this name already exists."]


def test_same_sub_vertical_name_in_different_verticals_is_fine(logged_client, verticals):
    r = _post(logged_client, {"name": "Agro", "sub_verticals": [_general(), _sub("Yellow line")]})
    assert r.status_code == 201


# --- Update ----------------------------------------------------------------------------------


def _current(client, vertical):
    return client.get(f"{URL}{vertical.pk}/").json()["sub_verticals"]


def test_update_without_sub_verticals_keeps_them(logged_client, verticals):
    industry = verticals["industry"]
    before = _subs(industry)
    assert _patch(logged_client, industry.pk, {"is_enabled": False}).status_code == 200
    assert _subs(industry) == before


def test_update_edits_adds_and_removes_sub_verticals(logged_client, verticals):
    industry = verticals["industry"]
    general, yellow = _current(logged_client, industry)
    r = _patch(
        logged_client,
        industry.pk,
        {
            "sub_verticals": [
                {**general, "risk": "high", "allowed_terms": [12, 24], "recommended_term": 12},
                {"name": "Machinery", "risk": "low", "allowed_terms": [60], "recommended_term": 60},
                # "Yellow line" is not sent: it is removed
            ]
        },
    )
    assert r.status_code == 200, r.json()
    assert _subs(industry) == [
        ("General", True, "high", [12, 24], 12),
        ("Machinery", False, "low", [60], 60),
    ]
    assert not SubVertical.objects.filter(pk=yellow["id"]).exists()


def test_update_can_rename_and_reuse_a_removed_name(logged_client, verticals):
    industry = verticals["industry"]
    general, yellow = _current(logged_client, industry)
    r = _patch(
        logged_client,
        industry.pk,
        {"sub_verticals": [general, _sub("Yellow line", risk="low")]},  # new item, same name
    )
    assert r.status_code == 200, r.json()
    assert [s[2] for s in _subs(industry)] == ["medium", "low"]


def test_general_cannot_be_removed_or_replaced(logged_client, verticals):
    industry = verticals["industry"]
    _general_item, yellow = _current(logged_client, industry)
    # Without the general
    assert _patch(logged_client, industry.pk, {"sub_verticals": [yellow]}).status_code == 400
    # With a brand-new general instead of the existing one
    r = _patch(logged_client, industry.pk, {"sub_verticals": [_general(), yellow]})
    assert r.status_code == 400
    # Turning a regular sub-vertical into the general one
    r = _patch(logged_client, industry.pk, {"sub_verticals": [{**yellow, "is_general": True}]})
    assert r.status_code == 400
    assert len(_subs(industry)) == 2


def test_cannot_touch_another_verticals_sub_vertical(logged_client, verticals):
    industry, it = verticals["industry"], verticals["it"]
    general = _current(logged_client, industry)[0]
    datacenter = _current(logged_client, it)[1]
    r = _patch(logged_client, industry.pk, {"sub_verticals": [general, datacenter]})
    assert r.status_code == 400
    assert SubVertical.objects.get(pk=datacenter["id"]).vertical == it


def test_failed_update_changes_nothing(logged_client, verticals):
    industry = verticals["industry"]
    before = _subs(industry)
    general, yellow = _current(logged_client, industry)
    r = _patch(
        logged_client,
        industry.pk,
        {"name": "Renamed", "sub_verticals": [general, {**yellow, "recommended_term": 99}]},
    )
    assert r.status_code == 400
    industry.refresh_from_db()
    assert industry.name == "Industry"
    assert _subs(industry) == before


# --- Delete ----------------------------------------------------------------------------------


def test_delete_removes_sub_verticals(logged_client, verticals, managers):
    assert logged_client.delete(f"{URL}{verticals['industry'].pk}/").status_code == 204
    assert not SubVertical.objects.filter(vertical_id=verticals["industry"].pk).exists()
    # The account managers (users) stay
    assert all(
        manager.__class__.objects.filter(pk=manager.pk).exists() for manager in managers.values()
    )


def test_only_active_account_managers_are_listed(logged_client, verticals, managers):
    def listed():
        rows = logged_client.get(URL, {"search": "industry"}).json()["results"]
        return [m["full_name"] for m in rows[0]["account_managers_detail"]]

    assert listed() == ["Ana Souza", "Bruno Lima"]
    # A deactivated user, or one who is no longer an account manager, is not shown
    managers["ana"].is_active = False
    managers["ana"].save()
    from users.models import Role

    Role.account_manager().users.remove(managers["bruno"])
    assert listed() == []


# --- Translations ----------------------------------------------------------------------------


def test_validation_messages_follow_user_language(logged_client, verticals):
    logged_client.patch(
        "/api/auth/preferences/", {"language": "pt-br"}, content_type="application/json"
    )
    r = _post(logged_client, {"name": "Industry"})
    assert r.json()["name"] == ["Já existe uma vertical com este nome."]
    r = _post(
        logged_client,
        {"name": "Agro", "sub_verticals": [_general(), _sub("A", recommended_term=48)]},
    )
    assert r.json()["sub_verticals"]["1"]["recommended_term"] == [
        "O prazo recomendado deve estar entre os prazos aceitos."
    ]


def test_general_display_name_is_translated(verticals):
    from django.utils import translation

    general = verticals["mining"].sub_verticals.get(is_general=True)
    with translation.override("pt-br"):
        assert str(general) == "Mining / Geral"
    with translation.override("es"):
        assert general.display_name == "General"


def test_vertical_keywords(logged_client):
    r = _post(logged_client, {"name": "Agribusiness", "keywords": ["Farm", "FARM", "Rural"]})
    assert r.status_code == 201, r.json()
    assert r.json()["keywords"] == ["farm", "rural"]
    found = logged_client.get(URL, {"search": "rur"}).json()["results"]
    assert [v["name"] for v in found] == ["Agribusiness"]


def test_vertical_column_filters(logged_client):
    Vertical.objects.create(name="Information Technology", keywords=["servers"])
    health = Vertical.objects.create(name="Healthcare")
    ana = make_account_manager("Ana", "Souza", "ana@example.com", verticals=[health])
    names = lambda params: [  # noqa: E731
        v["name"] for v in logged_client.get("/api/catalogs/verticals/", params).json()["results"]
    ]
    assert names({"name": "techn"}) == ["Information Technology"]
    assert names({"name": "server"}) == ["Information Technology"]
    assert names({"account_manager": ana.id}) == ["Healthcare"]
