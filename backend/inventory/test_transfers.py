"""Phase 6: transfers between warehouses — eligible assets (never held for a dispute), picking
against the list (RN-24), sending in transit keeping the status, receiving back to it at the
destination (RN-02), containers travelling with their assets, accessories, shortages,
surpluses and damage as occurrences, the alert for a late transfer (RN-25), the trail (RN-07)
and permissions."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from . import disposals, followups, services, transfers
from .conftest import client_for
from .models import (
    AccessoryBalance,
    Alert,
    Asset,
    Container,
    DisposalKind,
    EventKind,
    Location,
    Occurrence,
    OccurrenceKind,
    OccurrenceStatus,
    Transfer,
    TransferFileKind,
    TransferStatus,
    Warehouse,
)
from .states import AreaType, AssetStatus, DomainError

API = "/api/inventory"


@pytest.fixture
def recife(db):
    """The destination warehouse with a dock, a stock area and a scrap area."""
    warehouse = Warehouse.objects.create(name="CD Recife", state="PE")

    def make(segment, area_type):
        return Location.objects.create(
            warehouse=warehouse,
            segment=segment,
            code=f"{warehouse.code}-{segment}",
            area_type=area_type,
        )

    return {
        "warehouse": warehouse,
        "dock": make("DOC", AreaType.DOCK),
        "stock": make("EST", AreaType.STOCK),
        "scrap": make("SUC", AreaType.SCRAP),
    }


@pytest.fixture
def at(make_asset, places, admin):
    """An asset at the origin in a status (through the statuses, as the flow does)."""
    paths = {
        AssetStatus.AWAITING_INSPECTION: [(AssetStatus.AWAITING_INSPECTION, "queue")],
        AssetStatus.IN_INSPECTION: [
            (AssetStatus.AWAITING_INSPECTION, "queue"),
            (AssetStatus.IN_INSPECTION, "bench"),
        ],
        AssetStatus.AVAILABLE: [
            (AssetStatus.AWAITING_INSPECTION, "queue"),
            (AssetStatus.IN_INSPECTION, "bench"),
            (AssetStatus.AVAILABLE, "shelf"),
        ],
        AssetStatus.SCRAP: [
            (AssetStatus.AWAITING_INSPECTION, "queue"),
            (AssetStatus.IN_INSPECTION, "bench"),
            (AssetStatus.SCRAP, "scrap"),
        ],
    }

    def make(status=AssetStatus.AVAILABLE):
        asset = make_asset()
        for step, place in paths[status]:
            services.change_status(asset, to_status=step, user=admin, to_location=places[place])
        asset.refresh_from_db()
        return asset

    return make


def _pdf():
    return SimpleUploadedFile("nf.pdf", b"%PDF-1.4 test", content_type="application/pdf")


def _transfer(warehouse, recife, analyst, **kwargs):
    return transfers.create(
        origin=warehouse,
        destination=recife["warehouse"],
        reason="Sell in the Northeast",
        user=analyst,
        **kwargs,
    )


def _ready(transfer, user):
    transfers.update_header(transfer, fiscal_document_number="NF 77")
    transfers.add_file(transfer, kind=TransferFileKind.FISCAL_DOCUMENT, upload=_pdf(), user=user)


def _trail_matches(asset):
    asset.refresh_from_db()
    last = asset.events.exclude(kind=EventKind.LABEL_REPRINT).order_by("-at", "-id").first()
    return last.status_after == asset.status


# --- Request -----------------------------------------------------------------------------------


def test_request_rules(warehouse, recife, analyst):
    with pytest.raises(DomainError):
        transfers.create(origin=warehouse, destination=warehouse, reason="x", user=analyst)
    with pytest.raises(DomainError) as error:
        transfers.create(
            origin=warehouse, destination=recife["warehouse"], reason=" ", user=analyst
        )
    assert error.value.field == "reason"
    with pytest.raises(DomainError):
        _transfer(warehouse, recife, analyst, transit_days=0)
    assert _transfer(warehouse, recife, analyst).code.startswith("TRF-")


def test_eligible_assets(at, warehouse, recife, analyst, customer, admin):
    transfer = _transfer(warehouse, recife, analyst)
    for status in (AssetStatus.AVAILABLE, AssetStatus.SCRAP, AssetStatus.AWAITING_INSPECTION):
        transfers.add_asset(transfer, at(status))
    with pytest.raises(DomainError):  # in inspection
        transfers.add_asset(transfer, at(AssetStatus.IN_INSPECTION))
    held = at()
    Asset.objects.filter(pk=held.pk).update(held_for_dispute=True)
    with pytest.raises(DomainError) as error:
        transfers.add_asset(transfer, held)
    assert "dispute" in str(error.value.message)
    # Reserved for a disposal: not transferable
    reserved = at()
    sale = disposals.create(
        kind=DisposalKind.LESSEE_SALE, warehouse=warehouse, customer=customer, user=admin
    )
    disposals.add_asset(sale, reserved, user=admin)
    with pytest.raises(DomainError):
        transfers.add_asset(transfer, reserved)
    # In a transfer: not in another, nor reserved for a disposal
    first = transfer.items.first().asset
    with pytest.raises(DomainError):
        transfers.add_asset(_transfer(warehouse, recife, analyst), first)
    with pytest.raises(DomainError):
        disposals.add_asset(sale, first, user=admin)
    # Not at the origin
    other = _transfer(recife["warehouse"], {"warehouse": warehouse}, analyst)
    with pytest.raises(DomainError):
        transfers.add_asset(other, at())


def test_items_change_only_before_approval(at, warehouse, recife, analyst, supervisor):
    transfer = _transfer(warehouse, recife, analyst)
    with pytest.raises(DomainError):  # nothing to approve
        transfers.approve(transfer, user=supervisor)
    item = transfers.add_asset(transfer, at())
    transfers.approve(transfer, user=supervisor)
    with pytest.raises(DomainError):
        transfers.remove_item(item)
    with pytest.raises(DomainError):
        transfers.add_asset(transfer, at())


# --- Picking, sending, receiving ---------------------------------------------------------------


def test_full_flow_back_to_the_status_rn24(
    at, warehouse, recife, analyst, supervisor, storekeeper, receiver
):
    good, scrap, stranger = at(), at(AssetStatus.SCRAP), at()
    transfer = _transfer(warehouse, recife, analyst)
    transfers.add_asset(transfer, good)
    transfers.add_asset(transfer, scrap)
    transfers.approve(transfer, user=supervisor)

    with pytest.raises(DomainError) as error:  # not on the list
        transfers.pick(transfer, stranger, user=storekeeper)
    assert error.value.field == "code"
    transfers.pick(transfer, good, user=storekeeper)
    _ready(transfer, storekeeper)
    # RN-24: a divergence blocks the sending
    with pytest.raises(DomainError) as error:
        transfers.send(transfer, user=storekeeper)
    assert "not picked" in str(error.value.message)
    transfers.pick(transfer, scrap, user=storekeeper)
    transfers.send(transfer, user=storekeeper)
    transfer.refresh_from_db()
    assert transfer.status == TransferStatus.IN_TRANSIT
    for asset, before in ((good, AssetStatus.AVAILABLE), (scrap, AssetStatus.SCRAP)):
        asset.refresh_from_db()
        assert asset.status == AssetStatus.IN_TRANSIT
        assert asset.current_location == Location.transit()
        assert asset.status_before_transit == before
        assert _trail_matches(asset)

    # At the destination: a location of the destination; RN-02 by the status it comes back to
    with pytest.raises(DomainError):
        transfers.receive(transfer, good, location=recife["dock"], user=receiver)
    transfers.receive(transfer, good, location=recife["stock"], user=receiver)
    with pytest.raises(DomainError):  # twice
        transfers.receive(transfer, good, location=recife["stock"], user=receiver)
    transfers.receive(
        transfer, scrap, location=recife["scrap"], user=receiver, damaged=True, note="Crushed"
    )
    good.refresh_from_db()
    scrap.refresh_from_db()
    assert (good.status, good.current_location) == (AssetStatus.AVAILABLE, recife["stock"])
    assert (scrap.status, scrap.current_location) == (AssetStatus.SCRAP, recife["scrap"])
    assert _trail_matches(good) and _trail_matches(scrap)
    assert good.events.filter(kind=EventKind.TRANSFER_IN, document_ref=transfer.ref).exists()

    transfers.finish(transfer, user=receiver)
    transfer.refresh_from_db()
    # The damage (only an occurrence — decision) makes it a discrepancy
    assert transfer.status == TransferStatus.RECEIVED_WITH_DISCREPANCY
    damage = transfer.occurrences.get()
    assert (damage.kind, damage.asset, damage.description) == (
        OccurrenceKind.TRANSPORT_DAMAGE,
        scrap,
        "Crushed",
    )


def test_shortage_surplus_and_late_arrival(
    at, warehouse, recife, analyst, supervisor, storekeeper, receiver
):
    first, second, stranger = at(), at(), at()
    transfer = _transfer(warehouse, recife, analyst)
    transfers.add_asset(transfer, first)
    transfers.add_asset(transfer, second)
    transfers.approve(transfer, user=supervisor)
    transfers.pick(transfer, first, user=storekeeper)
    transfers.pick(transfer, second, user=storekeeper)
    _ready(transfer, storekeeper)
    transfers.send(transfer, user=storekeeper)

    # A surplus is refused but stays recorded (once)
    for _ in range(2):
        with pytest.raises(DomainError) as error:
            transfers.receive(transfer, stranger, location=recife["stock"], user=receiver)
        assert "surplus" in str(error.value.message)
    assert transfer.occurrences.filter(kind=OccurrenceKind.SURPLUS, asset=stranger).count() == 1

    transfers.receive(transfer, first, location=recife["stock"], user=receiver)
    transfers.finish(transfer, user=receiver)
    shortage = transfer.occurrences.get(kind=OccurrenceKind.SHORTAGE)
    assert shortage.asset == second
    second.refresh_from_db()
    assert second.status == AssetStatus.IN_TRANSIT  # until found
    # It arrives later: received, its shortage resolved
    transfers.receive(transfer, second, location=recife["stock"], user=receiver)
    shortage.refresh_from_db()
    assert shortage.status == OccurrenceStatus.RESOLVED


def test_containers_travel_with_their_assets(
    at, places, warehouse, recife, analyst, supervisor, storekeeper, receiver, admin
):
    pallet = services.create_container(kind="pallet", location=places["shelf"], user=admin)
    first, second = at(), at()
    for asset in (first, second):
        services.move_asset(asset, user=admin, to_container=pallet)
    transfer = _transfer(warehouse, recife, analyst)
    added = transfers.add_container(transfer, pallet)
    assert len(added) == 2
    transfers.approve(transfer, user=supervisor)
    transfers.pick(transfer, pallet, user=storekeeper)
    _ready(transfer, storekeeper)
    transfers.send(transfer, user=storekeeper)
    pallet.refresh_from_db()
    assert pallet.current_location == Location.transit()
    first.refresh_from_db()
    assert first.current_container == pallet
    # Moved by hand while in transit: refused
    with pytest.raises(DomainError):
        services.move_container(pallet, to_location=recife["stock"], user=admin)

    transfers.receive(transfer, pallet, location=recife["stock"], user=receiver)
    pallet.refresh_from_db()
    assert pallet.current_location == recife["stock"]
    for asset in (first, second):
        asset.refresh_from_db()
        assert (asset.status, asset.current_container) == (AssetStatus.AVAILABLE, pallet)
    transfers.finish(transfer, user=receiver)
    transfer.refresh_from_db()
    assert transfer.status == TransferStatus.RECEIVED


def test_container_with_an_asset_not_on_the_list_is_refused(
    at, places, warehouse, recife, analyst, supervisor, storekeeper, admin
):
    pallet = services.create_container(kind="pallet", location=places["shelf"], user=admin)
    listed = at()
    services.move_asset(listed, user=admin, to_container=pallet)
    transfer = _transfer(warehouse, recife, analyst)
    transfers.add_asset(transfer, listed)
    transfers.approve(transfer, user=supervisor)
    services.move_asset(at(), user=admin, to_container=pallet)
    with pytest.raises(DomainError):
        transfers.pick(transfer, pallet, user=storekeeper)


def test_accessories_and_cancelling(
    places, warehouse, recife, cables, analyst, supervisor, storekeeper, receiver, admin
):
    services.add_accessories(cables, 6, user=admin, location=places["shelf"])
    transfer = _transfer(warehouse, recife, analyst)
    with pytest.raises(DomainError):
        transfers.add_accessory(transfer, cables, 7)
    line = transfers.add_accessory(transfer, cables, 4)
    transfers.approve(transfer, user=supervisor)
    transfers.pick_accessory(transfer, line, 4, user=storekeeper, location=places["shelf"])
    assert AccessoryBalance.objects.get(location=places["shelf"]).quantity == 2
    _ready(transfer, storekeeper)
    transfers.send(transfer, user=storekeeper)
    line.refresh_from_db()
    with pytest.raises(DomainError):  # a location of the origin
        transfers.receive_accessory(transfer, line, 3, user=receiver, location=places["shelf"])
    transfers.receive_accessory(transfer, line, 3, user=receiver, location=recife["stock"])
    transfers.finish(transfer, user=receiver)
    assert AccessoryBalance.objects.get(location=recife["stock"]).quantity == 3
    shortage = transfer.occurrences.get(kind=OccurrenceKind.SHORTAGE)
    assert (shortage.asset_model, shortage.quantity) == (cables, 1)

    # Cancelling before sending gives the picked accessories back
    other = _transfer(warehouse, recife, analyst)
    line = transfers.add_accessory(other, cables, 2)
    transfers.approve(other, user=supervisor)
    transfers.pick_accessory(other, line, 2, user=storekeeper, location=places["shelf"])
    assert AccessoryBalance.objects.get(location=places["shelf"]).quantity == 0
    transfers.cancel(other, user=supervisor, reason="Not needed")
    assert AccessoryBalance.objects.get(location=places["shelf"]).quantity == 2
    other.refresh_from_db()
    assert other.status == TransferStatus.CANCELLED
    with pytest.raises(DomainError):  # sent ones are not cancelled
        transfers.cancel(transfer, user=supervisor, reason="x")


def test_sending_needs_the_fiscal_document(at, warehouse, recife, analyst, supervisor, storekeeper):
    asset = at()
    transfer = _transfer(warehouse, recife, analyst)
    transfers.add_asset(transfer, asset)
    transfers.approve(transfer, user=supervisor)
    transfers.pick(transfer, asset, user=storekeeper)
    found = " ".join(str(p) for p in transfers.problems(transfer))
    assert "fiscal document's number" in found and "Attach the fiscal document" in found


def test_a_dispute_before_sending_blocks_it(
    at, warehouse, recife, analyst, supervisor, storekeeper
):
    asset = at()
    transfer = _transfer(warehouse, recife, analyst)
    transfers.add_asset(transfer, asset)
    transfers.approve(transfer, user=supervisor)
    transfers.pick(transfer, asset, user=storekeeper)
    _ready(transfer, storekeeper)
    Asset.objects.filter(pk=asset.pk).update(held_for_dispute=True)
    with pytest.raises(DomainError) as error:
        transfers.send(transfer, user=storekeeper)
    assert "dispute" in str(error.value.message)


def test_transfer_events_are_not_reversed_by_hand(
    at, warehouse, recife, analyst, supervisor, storekeeper, admin
):
    asset = at()
    transfer = _transfer(warehouse, recife, analyst)
    transfers.add_asset(transfer, asset)
    transfers.approve(transfer, user=supervisor)
    transfers.pick(transfer, asset, user=storekeeper)
    _ready(transfer, storekeeper)
    transfers.send(transfer, user=storekeeper)
    event = asset.events.order_by("-at", "-id").first()
    with pytest.raises(DomainError):
        services.reverse_event(event, user=admin, reason="Oops")


# --- RN-25 ---------------------------------------------------------------------------------------


def test_late_transfer_alert_rn25(at, warehouse, recife, analyst, supervisor, storekeeper):
    asset = at()
    transfer = _transfer(warehouse, recife, analyst, transit_days=3)
    transfers.add_asset(transfer, asset)
    transfers.approve(transfer, user=supervisor)
    transfers.pick(transfer, asset, user=storekeeper)
    _ready(transfer, storekeeper)
    transfers.send(transfer, user=storekeeper)
    today = timezone.localdate()
    followups.check_deadlines(today + timedelta(days=3))
    assert not Alert.objects.filter(kind="transfer_late").exists()
    followups.check_deadlines(today + timedelta(days=5))
    followups.check_deadlines(today + timedelta(days=5))  # idempotent
    alert = Alert.objects.get(kind="transfer_late")
    assert alert.params["transfer"] == transfer.code and alert.params["days"] == 2


# --- API -------------------------------------------------------------------------------------


def test_api_flow_and_roles(
    client, at, warehouse, recife, analyst, supervisor, storekeeper, receiver, nobody
):
    asset = at()
    client_for(client, nobody)
    body = {"origin": warehouse.id, "destination": recife["warehouse"].id, "reason": "Stock"}
    assert (
        client.post(f"{API}/transfers/", body, content_type="application/json").status_code == 403
    )
    client_for(client, analyst)
    created = client.post(f"{API}/transfers/", body, content_type="application/json")
    assert created.status_code == 201, created.json()
    url = f"{API}/transfers/{created.json()['id']}/"
    data = client.post(
        f"{url}items/", {"code": asset.horizon_id}, content_type="application/json"
    ).json()
    assert data["items"][0]["asset_detail"]["horizon_id"] == asset.horizon_id
    assert any("approve" in p for p in data["problems"])
    assert client.post(f"{url}approve/").status_code == 403  # analysts do not approve
    client_for(client, supervisor)
    assert client.post(f"{url}approve/").json()["status"] == "approved"
    client_for(client, storekeeper)
    picked = client.post(
        f"{url}pick/", {"code": asset.horizon_id}, content_type="application/json"
    ).json()
    assert picked["status"] == "picking" and picked["items"][0]["picked"]
    client.post(f"{url}files/", {"kind": "fiscal_document", "file": _pdf()})
    client_for(client, analyst)
    client.patch(url, {"fiscal_document_number": "NF 1"}, content_type="application/json")
    client_for(client, storekeeper)
    sent = client.post(f"{url}send/")
    assert sent.json()["status"] == "in_transit", sent.json()
    client_for(client, receiver)
    missing = client.post(
        f"{url}receive/", {"code": asset.horizon_id}, content_type="application/json"
    )
    assert missing.json()["field"] == "location"
    received = client.post(
        f"{url}receive/",
        {"location": recife["stock"].code, "code": asset.horizon_id},
        content_type="application/json",
    ).json()
    assert received["items"][0]["received"]
    assert client.post(f"{url}finish/").json()["status"] == "received"
    listed = client.get(f"{API}/transfers/?search={created.json()['code']}").json()
    assert listed["count"] == 1 and listed["results"][0]["received_count"] == 1
    assert Transfer.objects.get().received_by == receiver
    assert Container.objects.count() == 0
    assert Occurrence.objects.count() == 0
