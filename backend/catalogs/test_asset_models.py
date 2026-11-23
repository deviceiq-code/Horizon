"""Asset models: a manufacturer's model of an asset class, described by its template."""

import pytest
from django.contrib.auth import get_user_model

from .models import AssetClass, AssetModel, Manufacturer, SubVertical, Vertical

URL = "/api/catalogs/asset-models/"

TEMPLATE = [
    {"key": "ram_gb", "label": "RAM", "kind": "number", "unit": "GB", "required": True},
    {"key": "panel", "label": "Panel", "kind": "choice", "unit": "", "required": False,
     "options": ["IPS", "OLED"]},
]  # fmt: skip


@pytest.fixture
def logged_client(client, db):
    user = get_user_model().objects.create_user("tester", password="strong-password-123")
    client.force_login(user)
    return client


@pytest.fixture
def catalog(db):
    vertical = Vertical.objects.create(name="Information Technology")
    sub = SubVertical.objects.create(vertical=vertical, **SubVertical.general_defaults())
    return {
        "notebook": AssetClass.objects.create(
            name="Notebook", plural_name="Notebooks", sub_vertical=sub, spec_template=TEMPLATE
        ),
        "monitor": AssetClass.objects.create(
            name="Monitor", plural_name="Monitors", sub_vertical=sub, spec_template=TEMPLATE[1:]
        ),
        "dell": Manufacturer.objects.create(name="Dell"),
        "lenovo": Manufacturer.objects.create(name="Lenovo"),
    }


def _post(client, data):
    return client.post(URL, data, content_type="application/json")


def _payload(catalog, **overrides):
    return {
        "manufacturer": catalog["dell"].id,
        "name": "  Latitude   5440 ",
        "asset_class": catalog["notebook"].id,
        "specs": {"ram_gb": "16", "panel": "ips"},
        "serial_regex": "[A-Z0-9]{7}",
        "kit_checklist": ["Charger", " charger ", "", "Battery"],
        "test_script": ["Boots", "Keyboard"],
        "has_storage": True,
        "keywords": ["Corporate"],
        **overrides,
    }


def test_create_asset_model(logged_client, catalog):
    response = _post(logged_client, _payload(catalog))
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["name"] == "Latitude 5440"
    assert data["manufacturer_name"] == "Dell"
    assert data["asset_class_detail"]["name"] == "Notebook"
    assert {f["key"]: f["value"] for f in data["spec_values"]} == {"ram_gb": "16", "panel": "IPS"}
    assert data["kit_checklist"] == ["Charger", "Battery"]
    assert data["tracking"] == "unit"
    assert data["keywords"] == ["corporate"]
    assert data["assets_count"] == 0


def test_model_values_are_optional_defaults(logged_client, catalog):
    """A required field may stay empty on the model (each asset fills it); the stored
    template keeps it required."""
    response = _post(logged_client, _payload(catalog, specs={}))
    assert response.status_code == 201, response.json()
    ram = response.json()["spec_values"][0]
    assert (ram["value"], ram["required"]) == ("", True)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"specs": {"panel": "CRT"}}, "specs"),
        ({"specs": {"unknown": "1"}}, "specs"),
        ({"serial_regex": "[A-Z"}, "serial_regex"),
        ({"name": "  "}, "name"),
        ({"tracking": "box"}, "tracking"),
    ],
)
def test_invalid_input(logged_client, catalog, overrides, field):
    response = _post(logged_client, _payload(catalog, **overrides))
    assert response.status_code == 400
    assert field in response.json()


def test_name_unique_per_manufacturer(logged_client, catalog):
    assert _post(logged_client, _payload(catalog)).status_code == 201
    response = _post(logged_client, _payload(catalog, name="latitude 5440"))
    assert "name" in response.json()
    # Another manufacturer may have it
    assert (
        _post(logged_client, _payload(catalog, manufacturer=catalog["lenovo"].id)).status_code
        == 201
    )


def test_disabled_choices_are_not_offered(logged_client, catalog):
    catalog["dell"].is_enabled = False
    catalog["dell"].save()
    response = _post(logged_client, _payload(catalog))
    assert "manufacturer" in response.json()


def test_changing_the_class_keeps_the_values_it_still_has(logged_client, catalog):
    created = _post(logged_client, _payload(catalog)).json()
    response = logged_client.patch(
        f"{URL}{created['id']}/",
        {"asset_class": catalog["monitor"].id},
        content_type="application/json",
    )
    assert response.status_code == 200, response.json()
    assert {f["key"]: f["value"] for f in response.json()["spec_values"]} == {"panel": "IPS"}


def test_filters(logged_client, catalog):
    _post(logged_client, _payload(catalog))
    _post(logged_client, _payload(catalog, manufacturer=catalog["lenovo"].id, name="ThinkPad T14"))
    names = lambda params: [m["name"] for m in logged_client.get(URL, params).json()["results"]]  # noqa: E731
    assert names({}) == ["Latitude 5440", "ThinkPad T14"]
    assert names({"manufacturer": catalog["lenovo"].id}) == ["ThinkPad T14"]
    assert names({"name": "dell"}) == ["Latitude 5440"]
    assert names({"name": "corporate"}) == ["Latitude 5440", "ThinkPad T14"]
    assert names({"search": "thinkpad"}) == ["ThinkPad T14"]


def test_in_use_cannot_be_deleted(logged_client, catalog):
    created = _post(logged_client, _payload(catalog)).json()
    model = AssetModel.objects.get(pk=created["id"])
    # The manufacturer and the asset class of a model cannot be deleted either
    assert (
        logged_client.delete(f"/api/catalogs/manufacturers/{catalog['dell'].id}/").status_code
        == 409
    )
    assert (
        logged_client.delete(f"/api/catalogs/asset-classes/{catalog['notebook'].id}/").status_code
        == 409
    )
    assert logged_client.delete(f"{URL}{model.id}/").status_code == 204
