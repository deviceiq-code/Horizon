"""Phase 7: inventory counts (blind readings, locations frozen while counting, divergences,
adjustments approved by a supervisor who did not count — RN-26), the location divergence
while moving (RN-19) and the indicators panel."""

from decimal import Decimal

import pytest

from . import counting, indicators, services
from .conftest import client_for, user_with_roles
from .counting import find_divergences
from .models import (
    AccessoryBalance,
    AdjustmentStatus,
    Alert,
    Asset,
    CountKind,
    CountStatus,
    DivergenceKind,
    EventKind,
    Location,
    Occurrence,
    OccurrenceKind,
)
from .states import AreaType, AssetStatus, DomainError

API = "/api/inventory"


@pytest.fixture
def stocked(make_asset, places, admin):
    """An available asset on a location (shelf by default)."""

    def make(place="shelf"):
        asset = make_asset()
        for status, where in (
            (AssetStatus.AWAITING_INSPECTION, "queue"),
            (AssetStatus.IN_INSPECTION, "bench"),
            (AssetStatus.AVAILABLE, place),
        ):
            services.change_status(asset, to_status=status, user=admin, to_location=places[where])
        asset.refresh_from_db()
        return asset

    return make


@pytest.fixture
def shelf2(places, warehouse):
    return Location.objects.create(
        warehouse=warehouse,
        parent=places["stock"],
        segment="A2",
        code=f"{places['stock'].code}-A2",
        area_type=AreaType.STOCK,
    )


@pytest.fixture
def other_supervisor(db):
    from users.models import INVENTORY_SUPERVISOR

    return user_with_roles("supervisor2", INVENTORY_SUPERVISOR)


# --- Divergences (pure) --------------------------------------------------------------------------


def test_find_divergences():
    result = find_divergences(
        scope={10, 11},
        expected_assets={1: 10, 2: 10, 3: 11},
        read_assets={1: 10, 2: 11, 4: 11},
        expected_balances={(7, "good", None, 10): 5, (7, "good", None, 99): 3},
        counted_balances={(7, "good", None, 10): 4},
    )
    kinds = [(d.kind, d.asset) for d in result.divergences]
    assert (DivergenceKind.NOT_FOUND, 3) in kinds
    assert (DivergenceKind.OTHER_LOCATION, 2) in kinds
    assert (DivergenceKind.UNEXPECTED, 4) in kinds
    balances = [d for d in result.divergences if d.kind == DivergenceKind.BALANCE]
    # Only places in the scope
    assert [(b.expected_quantity, b.counted_quantity) for b in balances] == [(5, 4)]
    assert (result.expected, result.matched) == (3, 1)


def test_indicator_helpers():
    assert indicators.ratio(1, 3) == Decimal("33.33333")
    assert indicators.ratio(1, 0) is None
    assert [indicators.band(d) for d in (0, 7, 8, 30, 31, 91, 400)] == [
        "0-7",
        "0-7",
        "8-30",
        "8-30",
        "31-90",
        "91+",
        "91+",
    ]
    rows = indicators.band_counts({"available": [1, 10, 100]})
    assert rows[0]["bands"] == {"0-7": 1, "8-30": 1, "31-90": 0, "91+": 1}
    assert rows[0]["max_days"] == 100


# --- Opening and freezing ---------------------------------------------------------------------


def test_cyclic_scope_includes_children_and_freezes_them(
    stocked, places, shelf2, warehouse, supervisor, admin
):
    asset = stocked()
    count = counting.open_count(
        warehouse=warehouse, kind=CountKind.CYCLIC, user=supervisor, locations=[places["stock"]]
    )
    scope = set(count.locations.values_list("code", flat=True))
    assert scope == {places["stock"].code, places["shelf"].code, shelf2.code}
    # Nothing moves in or out while counting
    with pytest.raises(DomainError) as error:
        services.move_asset(asset, user=admin, to_location=shelf2)
    assert count.code in str(error.value.message)
    # Overlapping counts are refused
    with pytest.raises(DomainError):
        counting.open_count(
            warehouse=warehouse, kind=CountKind.CYCLIC, user=supervisor, locations=[shelf2]
        )
    counting.cancel(count, user=supervisor, reason="Wrong day")
    services.move_asset(asset, user=admin, to_location=shelf2)  # free again


def test_general_count_takes_the_whole_warehouse(places, warehouse, supervisor):
    count = counting.open_count(warehouse=warehouse, kind=CountKind.GENERAL, user=supervisor)
    assert count.locations.count() == len(places)
    assert count.code.startswith("INV-")


# --- Counting, closing, adjusting --------------------------------------------------------------


def test_full_count_and_adjustments_rn26(
    stocked, places, shelf2, warehouse, cables, supervisor, storekeeper, other_supervisor, admin
):
    there, moved, lost = stocked(), stocked(), stocked()
    elsewhere = stocked()  # recorded at the shelf, counted outside the scope later
    services.move_asset(elsewhere, user=admin, to_location=places["stock"])
    outsider = stocked()
    services.move_asset(outsider, user=admin, to_location=places["stock"])
    services.add_accessories(cables, 10, user=admin, location=places["shelf"])

    count = counting.open_count(
        warehouse=warehouse,
        kind=CountKind.CYCLIC,
        user=supervisor,
        responsible=supervisor,
        locations=[places["shelf"], shelf2],
    )
    counting.read_asset(count, there, location=places["shelf"], user=storekeeper)
    counting.read_asset(count, moved, location=shelf2, user=storekeeper)
    counting.read_asset(count, outsider, location=shelf2, user=storekeeper)
    counting.read_accessories(count, cables, 6, location=places["shelf"], user=storekeeper)
    counting.read_accessories(count, cables, 2, location=places["shelf"], user=storekeeper)
    with pytest.raises(DomainError):  # outside the scope
        counting.read_asset(count, elsewhere, location=places["dock"], user=storekeeper)

    counting.close(count, user=storekeeper)
    count.refresh_from_db()
    assert count.status == CountStatus.CLOSED
    assert (count.expected_assets, count.matched_assets) == (3, 1)
    found = {(d.kind, d.asset_id) for d in count.divergences.all()}
    assert (DivergenceKind.NOT_FOUND, lost.pk) in found
    assert (DivergenceKind.OTHER_LOCATION, moved.pk) in found
    assert (DivergenceKind.UNEXPECTED, outsider.pk) in found
    balance = count.divergences.get(kind=DivergenceKind.BALANCE)
    assert (balance.expected_quantity, balance.counted_quantity) == (10, 8)

    # RN-26: not by who counted nor by the one responsible
    divergence = count.divergences.get(kind=DivergenceKind.NOT_FOUND)
    for user in (storekeeper, supervisor):
        with pytest.raises(DomainError) as error:
            counting.decide(divergence, user=user, approve=True, reason="Gone")
        assert "RN-26" in str(error.value.message)
    with pytest.raises(DomainError):  # a reason is required
        counting.decide(divergence, user=other_supervisor, approve=True, reason=" ")

    counting.decide(divergence, user=other_supervisor, approve=True, reason="Searched twice")
    lost.refresh_from_db()
    assert lost.status == AssetStatus.WRITTEN_OFF
    assert lost.events.filter(kind=EventKind.INVENTORY_ADJUSTMENT).exists()
    assert Occurrence.objects.filter(count=count, kind=OccurrenceKind.LOST, asset=lost).exists()

    for kind in (DivergenceKind.OTHER_LOCATION, DivergenceKind.UNEXPECTED):
        counting.decide(
            count.divergences.get(kind=kind), user=other_supervisor, approve=True, reason="Ok"
        )
    for asset in (moved, outsider):
        asset.refresh_from_db()
        assert asset.current_location == shelf2
    counting.decide(balance, user=other_supervisor, approve=False, reason="Recount next week")
    assert AccessoryBalance.objects.get(location=places["shelf"]).quantity == 10
    count.refresh_from_db()
    assert count.status == CountStatus.FINISHED
    balance.refresh_from_db()
    assert balance.status == AdjustmentStatus.REJECTED


def test_balance_adjustment_and_lost_asset_found_again(
    stocked, places, warehouse, cables, supervisor, storekeeper, other_supervisor, admin
):
    lost = stocked()
    services.add_accessories(cables, 4, user=admin, location=places["shelf"])
    first = counting.open_count(
        warehouse=warehouse, kind=CountKind.CYCLIC, user=supervisor, locations=[places["shelf"]]
    )
    counting.read_accessories(first, cables, 7, location=places["shelf"], user=storekeeper)
    counting.close(first, user=storekeeper)
    for divergence in first.divergences.all():
        counting.decide(divergence, user=other_supervisor, approve=True, reason="Counted")
    assert AccessoryBalance.objects.get(location=places["shelf"]).quantity == 7
    lost.refresh_from_db()
    assert lost.status == AssetStatus.WRITTEN_OFF

    # A later count finds it: brought back in the status it had
    second = counting.open_count(
        warehouse=warehouse, kind=CountKind.CYCLIC, user=supervisor, locations=[places["shelf"]]
    )
    counting.read_asset(second, lost, location=places["shelf"], user=storekeeper)
    counting.read_accessories(second, cables, 7, location=places["shelf"], user=storekeeper)
    counting.close(second, user=storekeeper)
    divergence = second.divergences.get()
    assert divergence.kind == DivergenceKind.UNEXPECTED
    counting.decide(divergence, user=other_supervisor, approve=True, reason="Found")
    lost.refresh_from_db()
    assert lost.status == AssetStatus.AVAILABLE


def test_count_without_divergences_finishes(stocked, places, warehouse, supervisor, storekeeper):
    asset = stocked()
    count = counting.open_count(
        warehouse=warehouse, kind=CountKind.CYCLIC, user=supervisor, locations=[places["shelf"]]
    )
    counting.read_asset(count, asset, location=places["shelf"], user=storekeeper)
    counting.close(count, user=storekeeper)
    count.refresh_from_db()
    assert count.status == CountStatus.FINISHED
    assert count.matched_assets == 1


# --- RN-19 -------------------------------------------------------------------------------------


def test_movement_with_a_different_origin_rn19(client, stocked, places, shelf2, storekeeper):
    asset = stocked()
    client_for(client, storekeeper)
    response = client.post(
        f"{API}/movements/",
        {
            "origin_code": places["stock"].code,
            "object_code": asset.horizon_id,
            "destination_code": shelf2.code,
        },
        content_type="application/json",
    )
    assert response.status_code == 201, response.json()
    assert places["shelf"].code in response.json()["location_mismatch"]
    asset.refresh_from_db()
    assert asset.current_location == shelf2  # not blocked
    occurrence = Occurrence.objects.get(kind=OccurrenceKind.LOCATION_MISMATCH)
    assert occurrence.asset == asset and occurrence.lot is None
    assert Alert.objects.filter(kind="location_mismatch").count() == 1
    # The same origin as recorded: nothing
    again = client.post(
        f"{API}/movements/",
        {
            "origin_code": shelf2.code,
            "object_code": asset.horizon_id,
            "destination_code": places["shelf"].code,
        },
        content_type="application/json",
    ).json()
    assert again["location_mismatch"] is None
    listed = client.get(f"{API}/occurrences/?source=movement").json()
    assert listed["count"] == 1


# --- API ---------------------------------------------------------------------------------------


def test_api_counts_and_indicators(
    client, stocked, places, warehouse, supervisor, storekeeper, other_supervisor, nobody
):
    asset = stocked()
    client_for(client, storekeeper)
    body = {"warehouse": warehouse.id, "kind": "cyclic", "locations": [places["shelf"].id]}
    assert client.post(f"{API}/counts/", body, content_type="application/json").status_code == 403
    client_for(client, supervisor)
    created = client.post(f"{API}/counts/", body, content_type="application/json")
    assert created.status_code == 201, created.json()
    url = f"{API}/counts/{created.json()['id']}/"
    client_for(client, storekeeper)
    read = client.post(
        f"{url}readings/",
        {"location": places["shelf"].code, "code": asset.horizon_id},
        content_type="application/json",
    ).json()
    assert read[0]["asset_code"] == asset.horizon_id
    closed = client.post(f"{url}close/").json()
    assert closed["status"] == "finished" and closed["accuracy"] == "100.00000"
    client_for(client, nobody)
    assert client.post(f"{url}readings/", {}, content_type="application/json").status_code == 403
    panel = client.get(f"{API}/indicators/?warehouse={warehouse.id}").json()
    assert panel["location_accuracy"]["percent"] == "100.00000"
    assert panel["aging"][0]["status"] == "available"
    assert panel["lead_time"]["units"] == 1
    assert Asset.objects.filter(pk=asset.pk, status=AssetStatus.AVAILABLE).exists()
