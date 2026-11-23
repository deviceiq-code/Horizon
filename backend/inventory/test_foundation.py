"""Inventory foundation: warehouses' codes, locations, containers, assets, the movement service
and its API (RN-02, RN-05, RN-07, RN-08, RN-15, RN-16), immutable events, label ranges."""

import pytest
from django.db import IntegrityError, transaction

from . import services
from .codes import format_code
from .conftest import client_for
from .models import (
    Asset,
    Container,
    EventKind,
    ImmutableError,
    LabelRange,
    Location,
    MovementEvent,
    SerialStatus,
    Warehouse,
)
from .states import AreaType, AssetStatus, DomainError

S = AssetStatus
API = "/api/inventory"


def _post(client, url, data):
    return client.post(url, data, content_type="application/json")


# --- Warehouses' codes -----------------------------------------------------------------------


def test_warehouse_codes_are_generated_and_never_change(db):
    first = Warehouse.objects.create(name="CD Campinas", state="SP")
    second = Warehouse.objects.create(name="CD Jundiaí", state="SP")
    recife = Warehouse.objects.create(name="CD Recife", state="PE")
    abroad = Warehouse.objects.create(name="Miami", country="US")
    assert [w.code for w in (first, second, recife, abroad)] == ["SP01", "SP02", "PE01", "US01"]
    first.state = "RJ"
    first.save()
    first.refresh_from_db()
    assert first.code == "SP01"


def test_warehouse_code_is_read_only_in_the_api(client, admin, warehouse):
    client_for(client, admin)
    response = client.patch(
        f"{API}/warehouses/{warehouse.id}/", {"code": "XX99"}, content_type="application/json"
    )
    assert response.status_code == 200
    assert response.json()["code"] == "SP01"


# --- Locations -------------------------------------------------------------------------------


def test_transit_location_exists(db):
    transit = Location.transit()
    assert transit.warehouse is None
    assert transit.area_type == AreaType.VIRTUAL_TRANSIT


def test_create_locations_as_a_tree(client, supervisor, warehouse):
    client_for(client, supervisor)
    area = _post(
        client,
        f"{API}/locations/",
        {"warehouse": warehouse.id, "segment": " est ", "area_type": "stock"},
    )
    assert area.status_code == 201, area.json()
    assert area.json()["code"] == "SP01-EST"
    shelf = _post(client, f"{API}/locations/", {"parent": area.json()["id"], "segment": "03"})
    assert shelf.status_code == 201, shelf.json()
    # The child gets the warehouse and the area type of its parent
    assert shelf.json()["code"] == "SP01-EST-03"
    assert shelf.json()["warehouse"] == warehouse.id
    assert shelf.json()["area_type"] == "stock"
    assert shelf.json()["accepted_statuses"] == ["available", "reserved"]

    tree = client.get(f"{API}/locations/tree/", {"warehouse": warehouse.id}).json()
    assert [n["code"] for n in tree] == ["SP01-EST"]
    assert [n["code"] for n in tree[0]["children"]] == ["SP01-EST-03"]

    duplicate = _post(client, f"{API}/locations/", {"parent": area.json()["id"], "segment": "03"})
    assert "segment" in duplicate.json()
    bad = _post(
        client,
        f"{API}/locations/",
        {"warehouse": warehouse.id, "segment": "A B!", "area_type": "dock"},
    )
    assert "segment" in bad.json()
    virtual = _post(
        client,
        f"{API}/locations/",
        {"warehouse": warehouse.id, "segment": "V", "area_type": "virtual_transit"},
    )
    assert "area_type" in virtual.json()


def test_location_code_never_changes(client, supervisor, places):
    client_for(client, supervisor)
    response = client.patch(
        f"{API}/locations/{places['stock'].id}/",
        {"segment": "XYZ"},
        content_type="application/json",
    )
    assert "segment" in response.json()


def test_area_type_change_must_fit_the_assets_there(client, supervisor, places, make_asset):
    make_asset()  # in triage at the dock
    client_for(client, supervisor)
    url = f"{API}/locations/{places['dock'].id}/"
    response = client.patch(url, {"area_type": "stock"}, content_type="application/json")
    assert "area_type" in response.json()
    response = client.patch(url, {"is_active": False}, content_type="application/json")
    assert "is_active" in response.json()


def test_locations_need_a_supervisor_to_write(client, storekeeper, warehouse):
    client_for(client, storekeeper)
    assert client.get(f"{API}/locations/").status_code == 200
    response = _post(
        client,
        f"{API}/locations/",
        {"warehouse": warehouse.id, "segment": "X", "area_type": "dock"},
    )
    assert response.status_code == 403


def test_location_with_history_cannot_be_deleted(client, supervisor, places, make_asset):
    make_asset()
    client_for(client, supervisor)
    assert client.delete(f"{API}/locations/{places['dock'].id}/").status_code == 409
    assert client.delete(f"{API}/locations/{places['scrap'].id}/").status_code == 204
    transit = Location.transit()
    assert client.delete(f"{API}/locations/{transit.id}/").status_code == 409


# --- Containers --------------------------------------------------------------------------------


def test_create_container(client, receiver, places):
    client_for(client, receiver)
    response = _post(
        client, f"{API}/containers/", {"kind": "box", "current_location": places["dock"].id}
    )
    assert response.status_code == 201, response.json()
    code = response.json()["code"]
    assert code.startswith("C") and len(code) == 10
    container = Container.objects.get(code=code)
    assert container.events.get().kind == EventKind.ENTRY
    second = _post(
        client, f"{API}/containers/", {"kind": "pallet", "current_location": places["dock"].id}
    )
    assert second.json()["code"] != code
    assert client.delete(f"{API}/containers/{container.id}/").status_code == 409


# --- Entry (manual, until triage) ------------------------------------------------------------


def test_register_entry(make_asset, notebook, places):
    asset = make_asset("abc 1234")
    assert asset.horizon_id.startswith("H") and len(asset.horizon_id) == 10
    assert asset.serial == "ABC1234"
    assert asset.status == S.IN_TRIAGE
    assert asset.current_location == places["dock"]
    # Its specification values start as the model's
    assert {f["key"]: f["value"] for f in asset.specs} == {"ram_gb": "16", "color": ""}
    event = asset.events.get()
    assert (event.kind, event.status_after, event.to_location) == (
        EventKind.ENTRY,
        S.IN_TRIAGE,
        places["dock"],
    )


def test_serial_unique_per_model_rn05(make_asset):
    make_asset("ABC1234")
    with pytest.raises(DomainError):
        make_asset("ABC1234")
    # The database guards it too
    first = Asset.objects.get(serial="ABC1234")
    with pytest.raises(IntegrityError), transaction.atomic():
        Asset.objects.create(
            horizon_id=format_code("H", 99999999),
            asset_model=first.asset_model,
            serial="ABC1234",
            serial_status=SerialStatus.CAPTURED,
            status=S.IN_TRIAGE,
            current_location=first.current_location,
            created_by=first.created_by,
        )


def test_serial_follows_the_models_pattern(make_asset):
    with pytest.raises(DomainError) as exc:
        make_asset("ABC-12")
    assert exc.value.field == "serial"


def test_without_serial_a_reason_is_required(make_asset):
    with pytest.raises(DomainError):
        make_asset("")
    pending = make_asset("", no_serial_reason="needs_power_on")
    assert pending.serial_status == SerialStatus.PENDING
    none = make_asset("", no_serial_reason="item_has_none")
    assert none.serial_status == SerialStatus.NONE


def test_entry_only_at_a_dock_rn02(notebook, places, admin):
    with pytest.raises(DomainError):
        services.register_entry(
            asset_model=notebook, location=places["stock"], user=admin, serial="ABC1234"
        )


def test_quantity_models_have_no_units(cables, places, admin):
    with pytest.raises(DomainError):
        services.register_entry(asset_model=cables, location=places["dock"], user=admin)


def test_entry_api_is_for_administrators(client, admin, receiver, notebook, places):
    payload = {"asset_model": notebook.id, "location": places["dock"].code, "serial": "ABC1234"}
    assert _post(client_for(client, receiver), f"{API}/assets/", payload).status_code == 403
    response = _post(client_for(client, admin), f"{API}/assets/", payload)
    assert response.status_code == 201, response.json()
    assert response.json()["current_location_detail"]["code"] == "SP01-DOC"


# --- Horizon IDs and labels (RN-15, RN-16) -------------------------------------------------


def test_label_range_is_contiguous_and_binds_once(client, receiver, make_asset):
    client_for(client, receiver)
    response = _post(client, f"{API}/label-ranges/", {"count": 5})
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["size"] == 5
    assert data["last_number"] - data["first_number"] == 4
    assert data["first_code"] == format_code("H", data["first_number"])
    # The next ID is after the range
    assert services.new_horizon_id() == format_code("H", data["last_number"] + 1)

    reserved = format_code("H", data["first_number"] + 2)
    asset = make_asset(horizon_id=reserved)
    assert asset.horizon_id == reserved
    with pytest.raises(DomainError):  # already bound
        make_asset(horizon_id=reserved)
    with pytest.raises(DomainError):  # wrong check digit
        make_asset(horizon_id=reserved[:-1] + str((int(reserved[-1]) + 1) % 10))
    with pytest.raises(DomainError):  # never reserved
        make_asset(horizon_id=format_code("H", data["last_number"] + 500))
    assert _post(client, f"{API}/label-ranges/", {"count": 1001}).status_code == 400
    assert LabelRange.objects.count() == 1


def test_reprint_keeps_the_id_rn16(client, receiver, make_asset):
    asset = make_asset()
    client_for(client, receiver)
    response = _post(client, f"{API}/assets/{asset.id}/reprint/", {})
    assert response.status_code == 200
    assert response.json()["horizon_id"] == asset.horizon_id
    assert asset.events.filter(kind=EventKind.LABEL_REPRINT).count() == 1


def test_lookup_checks_the_digit_rn15(client, storekeeper, make_asset, places):
    asset = make_asset()
    client_for(client, storekeeper)
    found = client.get(f"{API}/lookup/", {"code": asset.horizon_id.lower()})
    assert found.json()["kind"] == "asset"
    assert found.json()["item"]["id"] == asset.id
    typo = asset.horizon_id[:-1] + str((int(asset.horizon_id[-1]) + 1) % 10)
    wrong = client.get(f"{API}/lookup/", {"code": typo})
    assert wrong.status_code == 400
    assert "check digit" in wrong.json()["detail"]
    assert client.get(f"{API}/lookup/", {"code": places["shelf"].code}).json()["kind"] == "location"
    missing = client.get(f"{API}/lookup/", {"code": format_code("H", 77777777)})
    assert missing.status_code == 400


# --- Movements (RN-02, RN-07, RN-08) -------------------------------------------------------


def _to_stock(asset, user, places):
    """Take an asset through triage and inspection to available stock."""
    for status, place in (
        (S.AWAITING_INSPECTION, places["queue"]),
        (S.IN_INSPECTION, places["bench"]),
        (S.AVAILABLE, places["stock"]),
    ):
        services.change_status(asset, to_status=status, user=user, to_location=place)
    asset.refresh_from_db()
    return asset


def test_move_by_reading_codes(client, storekeeper, admin, make_asset, places):
    asset = _to_stock(make_asset(), admin, places)
    client_for(client, storekeeper)
    response = _post(
        client,
        f"{API}/movements/",
        {"object_code": asset.horizon_id, "destination_code": places["shelf"].code.lower()},
    )
    assert response.status_code == 201, response.json()
    assert response.json()["to_location_code"] == "SP01-EST-A1"
    asset.refresh_from_db()
    assert asset.current_location == places["shelf"]


def test_area_must_take_the_status_rn02(client, storekeeper, make_asset, places):
    asset = make_asset()  # in triage
    client_for(client, storekeeper)
    response = _post(
        client,
        f"{API}/movements/",
        {"object_code": asset.horizon_id, "destination_code": places["stock"].code},
    )
    assert response.status_code == 400
    assert response.json()["field"] == "destination"
    asset.refresh_from_db()
    assert asset.current_location == places["dock"]
    assert asset.events.count() == 1


def test_nothing_goes_in_transit_by_hand(make_asset, places, admin):
    asset = make_asset()
    with pytest.raises(DomainError):
        services.move_asset(asset, user=admin, to_location=Location.transit())


def test_asset_into_a_container_and_container_moves_everything_rn08(
    client, storekeeper, admin, make_asset, places
):
    box = services.create_container(kind="box", location=places["dock"], user=admin)
    first, second = make_asset(), make_asset()
    client_for(client, storekeeper)
    for asset in (first, second):
        response = _post(
            client,
            f"{API}/movements/",
            {"object_code": asset.horizon_id, "destination_code": box.code},
        )
        assert response.status_code == 201, response.json()

    # The dock's assets cannot go to stock: nothing moves
    refused = _post(
        client,
        f"{API}/movements/",
        {"object_code": box.code, "destination_code": places["stock"].code},
    )
    assert refused.status_code == 400
    assert first.horizon_id in refused.json()["detail"]

    for asset in (first, second):
        services.change_status(asset, to_status=S.AWAITING_INSPECTION, user=admin)
    response = _post(
        client,
        f"{API}/movements/",
        {"object_code": box.code, "destination_code": places["queue"].code},
    )
    assert response.status_code == 201, response.json()
    parent = MovementEvent.objects.get(pk=response.json()["id"])
    assert parent.container == box
    assert sorted(e.asset_id for e in parent.child_events.all()) == sorted([first.id, second.id])
    for asset in (first, second):
        asset.refresh_from_db()
        assert asset.current_location == places["queue"]
        assert asset.current_container == box
    box.refresh_from_db()
    assert box.current_location == places["queue"]


def test_moving_needs_a_role(client, nobody, make_asset, places):
    asset = make_asset()
    client_for(client, nobody)
    response = _post(
        client,
        f"{API}/movements/",
        {"object_code": asset.horizon_id, "destination_code": places["dock"].code},
    )
    assert response.status_code == 403


def test_status_always_matches_the_latest_event_rn07(make_asset, places, admin):
    """After a scripted sequence of operations, every asset's status and place are those of its
    latest event (the service is the only writer)."""
    assets = [make_asset() for _ in range(3)]
    box = services.create_container(kind="cage", location=places["dock"], user=admin)
    services.move_asset(assets[0], user=admin, to_container=box)
    _to_stock(assets[1], admin, places)
    services.move_asset(assets[1], user=admin, to_location=places["shelf"])
    services.change_status(
        assets[1], to_status=S.BLOCKED, user=admin, to_location=places["quarantine"]
    )
    services.change_status(assets[2], to_status=S.IN_TRANSIT, user=admin)
    services.change_status(assets[2], to_status=S.IN_TRIAGE, user=admin, to_location=places["dock"])
    services.reprint_label(assets[0], user=admin)

    for asset in Asset.objects.all():
        latest = asset.events.exclude(kind=EventKind.LABEL_REPRINT).order_by("-at", "-id").first()
        assert asset.status == latest.status_after
        assert asset.current_location == latest.to_location
        assert asset.current_container == latest.to_container


def test_in_transit_comes_back_to_the_previous_status(make_asset, places, admin):
    asset = make_asset()
    services.change_status(asset, to_status=S.IN_TRANSIT, user=admin)
    asset.refresh_from_db()
    assert (asset.status, asset.current_location) == (S.IN_TRANSIT, Location.transit())
    with pytest.raises(DomainError):
        services.change_status(asset, to_status=S.AVAILABLE, user=admin)
    with pytest.raises(DomainError):  # moving by hand while in transit
        services.move_asset(asset, user=admin, to_location=places["dock"])


def test_invalid_transition_is_refused_rn01(make_asset, admin):
    asset = make_asset()
    with pytest.raises(DomainError):
        services.change_status(asset, to_status=S.AVAILABLE, user=admin)
    asset.refresh_from_db()
    assert asset.status == S.IN_TRIAGE


# --- Events are immutable; corrections are reversals ---------------------------------------


def test_events_cannot_be_changed_or_deleted(make_asset):
    event = make_asset().events.get()
    event.reason = "changed"
    with pytest.raises(ImmutableError):
        event.save()
    with pytest.raises(ImmutableError):
        event.delete()


def test_reverse_the_latest_event(client, supervisor, storekeeper, admin, make_asset, places):
    asset = _to_stock(make_asset(), admin, places)
    move = services.move_asset(asset, user=admin, to_location=places["shelf"])
    client_for(client, storekeeper)
    assert (
        _post(client, f"{API}/movements/{move.id}/reverse/", {"reason": "Wrong shelf"}).status_code
        == 403
    )
    client_for(client, supervisor)
    assert _post(client, f"{API}/movements/{move.id}/reverse/", {"reason": ""}).status_code == 400
    response = _post(client, f"{API}/movements/{move.id}/reverse/", {"reason": "Wrong shelf"})
    assert response.status_code == 201, response.json()
    asset.refresh_from_db()
    assert asset.current_location == places["stock"]
    reversal = MovementEvent.objects.get(pk=response.json()["id"])
    assert (reversal.kind, reversal.reverses) == (EventKind.REVERSAL, move)
    # Only the latest one
    assert (
        _post(client, f"{API}/movements/{move.id}/reverse/", {"reason": "Again"}).status_code == 400
    )


def test_asset_detail_has_its_history(client, storekeeper, admin, make_asset, places):
    asset = _to_stock(make_asset(), admin, places)
    client_for(client, storekeeper)
    data = client.get(f"{API}/assets/{asset.id}/").json()
    assert [e["kind"] for e in data["events"]] == ["status_change"] * 3 + ["entry"]
    assert data["warehouse"]["code"] == "SP01"
    listed = client.get(f"{API}/assets/", {"status": "available"}).json()["results"]
    assert [a["horizon_id"] for a in listed] == [asset.horizon_id]
    # Status and place are never written through the API
    client.patch(
        f"{API}/assets/{asset.id}/",
        {"status": "scrap", "notes": "Scratch"},
        content_type="application/json",
    )
    asset.refresh_from_db()
    assert (asset.status, asset.notes) == (S.AVAILABLE, "Scratch")
