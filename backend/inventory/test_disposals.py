"""Phase 5: stock query and disposals — reservation (a held asset is never reserved), picking
against the list, shipping (RN-23: a discard needs its certificate), cancelling, accessories,
parts recorded by taking scrap apart, the trail (RN-07) and permissions."""

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError

from entities.models import Buyer
from service_providers.models import ServiceKind, ServiceProvider

from . import disposals, inspection, services
from .conftest import client_for
from .models import (
    AccessoryBalance,
    Appointment,
    AppointmentKind,
    AppointmentStatus,
    Asset,
    Disposal,
    DisposalFileKind,
    DisposalKind,
    DisposalStatus,
    EventKind,
    Location,
    MovementEvent,
)
from .states import AreaType, AssetStatus, DomainError

API = "/api/inventory"


@pytest.fixture
def shipping(places, warehouse):
    return Location.objects.create(
        warehouse=warehouse,
        segment="EXP",
        code=f"{warehouse.code}-EXP",
        area_type=AreaType.SHIPPING,
    )


@pytest.fixture
def available(make_asset, places, admin):
    """An asset available on the shelf (through the statuses, as inspection does)."""

    def make(**kwargs):
        asset = make_asset(**kwargs)
        for status, place in (
            (AssetStatus.AWAITING_INSPECTION, places["queue"]),
            (AssetStatus.IN_INSPECTION, places["bench"]),
            (AssetStatus.AVAILABLE, places["shelf"]),
        ):
            services.change_status(asset, to_status=status, user=admin, to_location=place)
        asset.refresh_from_db()
        return asset

    return make


@pytest.fixture
def scrap(make_asset, places, admin):
    asset = make_asset()
    for status, place in (
        (AssetStatus.AWAITING_INSPECTION, places["queue"]),
        (AssetStatus.IN_INSPECTION, places["bench"]),
        (AssetStatus.SCRAP, places["scrap"]),
    ):
        services.change_status(asset, to_status=status, user=admin, to_location=place)
    asset.refresh_from_db()
    return asset


@pytest.fixture
def recycler(db):
    return ServiceProvider.objects.create(
        name="Recicla Ltda", tax_id="11444777000161", services=[ServiceKind.DISPOSAL]
    )


def _file(name="nf.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")


def _sale(warehouse, customer, user, **kwargs):
    return disposals.create(
        kind=DisposalKind.LESSEE_SALE, warehouse=warehouse, customer=customer, user=user, **kwargs
    )


def _ready(disposal, user):
    """Document number and file."""
    disposals.update_header(disposal, document_number="NF 123")
    disposals.add_file(disposal, kind=DisposalFileKind.DOCUMENT, upload=_file(), user=user)


def _trail_matches(asset):
    """RN-07: the asset mirrors its latest event."""
    asset.refresh_from_db()
    last = asset.events.exclude(kind=EventKind.LABEL_REPRINT).order_by("-at", "-id").first()
    return last.status_after == asset.status


# --- Header ------------------------------------------------------------------------------------


def test_header_rules_by_kind(warehouse, customer, recycler, admin):
    with pytest.raises(DomainError) as error:
        disposals.create(kind=DisposalKind.LESSEE_SALE, warehouse=warehouse, user=admin)
    assert error.value.field == "customer"
    with pytest.raises(DomainError):
        disposals.create(kind=DisposalKind.DISCARD, warehouse=warehouse, user=admin)
    with pytest.raises(DomainError):
        disposals.create(kind=DisposalKind.PARTS, warehouse=warehouse, user=admin)
    trucks = ServiceProvider.objects.create(
        name="Fretes", tax_id="11222333000181", services=[ServiceKind.TRANSPORT]
    )
    with pytest.raises(DomainError) as error:
        disposals.create(
            kind=DisposalKind.DISCARD, warehouse=warehouse, user=admin, discard_provider=trucks
        )
    assert error.value.field == "discard_provider"
    discard = disposals.create(
        kind=DisposalKind.DISCARD,
        warehouse=warehouse,
        user=admin,
        discard_provider=recycler,
        customer=customer,  # not kept: a discard has no customer
    )
    assert discard.customer is None
    assert discard.code.startswith("DSP-")
    relocation = disposals.create(
        kind=DisposalKind.RELOCATION,
        warehouse=warehouse,
        user=admin,
        customer=customer,
        contract=" CT-77 ",
    )
    assert relocation.contract == "CT-77"


def test_a_third_party_sale_has_a_buyer_not_a_customer(warehouse, customer, admin):
    with pytest.raises(DomainError) as error:
        disposals.create(
            kind=DisposalKind.THIRD_PARTY_SALE, warehouse=warehouse, user=admin, customer=customer
        )
    assert error.value.field == "buyer"
    buyer = Buyer.objects.create(entity=customer.entity)  # the same entity, another role
    sale = disposals.create(
        kind=DisposalKind.THIRD_PARTY_SALE,
        warehouse=warehouse,
        user=admin,
        customer=customer,  # not kept: the buyer is who it is sold to
        buyer=buyer,
    )
    assert (sale.buyer, sale.customer) == (buyer, None)
    # An inactive buyer is refused
    buyer.is_active = False
    buyer.save()
    with pytest.raises(DomainError) as error:
        disposals.update_header(sale, buyer=buyer)
    assert error.value.field == "buyer"
    # Nor can the role be removed while it bought something
    with pytest.raises(ProtectedError):
        buyer.delete()


# --- Reservation -------------------------------------------------------------------------------


def test_reserve_and_remove(available, warehouse, customer, admin):
    asset = available()
    sale = _sale(warehouse, customer, admin)
    item = disposals.add_asset(sale, asset, user=admin, unit_value=Decimal("1500"))
    asset.refresh_from_db()
    assert asset.status == AssetStatus.RESERVED
    assert _trail_matches(asset)
    # Not twice, nor in another disposal
    with pytest.raises(DomainError):
        disposals.add_asset(_sale(warehouse, customer, admin), asset, user=admin)
    disposals.remove_item(item, user=admin)
    asset.refresh_from_db()
    assert asset.status == AssetStatus.AVAILABLE
    assert _trail_matches(asset)


def test_a_held_asset_is_never_reserved(available, warehouse, customer, admin):
    asset = available()
    Asset.objects.filter(pk=asset.pk).update(held_for_dispute=True)
    with pytest.raises(DomainError) as error:
        disposals.add_asset(_sale(warehouse, customer, admin), asset, user=admin)
    assert "dispute" in str(error.value.message)
    asset.refresh_from_db()
    assert asset.status == AssetStatus.AVAILABLE


def test_only_available_assets_scrap_only_in_discards(
    make_asset, scrap, warehouse, customer, recycler, admin
):
    with pytest.raises(DomainError):
        disposals.add_asset(_sale(warehouse, customer, admin), make_asset(), user=admin)
    with pytest.raises(DomainError):
        disposals.add_asset(_sale(warehouse, customer, admin), scrap, user=admin)
    discard = disposals.create(
        kind=DisposalKind.DISCARD, warehouse=warehouse, user=admin, discard_provider=recycler
    )
    disposals.add_asset(discard, scrap, user=admin)
    scrap.refresh_from_db()
    assert scrap.status == AssetStatus.SCRAP  # stays scrap (decision)
    # Taken apart while in a disposal: refused
    with pytest.raises(DomainError):
        inspection.disassemble(scrap, user=admin, parts=[{"asset_model": scrap.asset_model}])


def test_asset_at_another_warehouse_is_refused(available, customer, admin):
    from .models import Warehouse

    other = Warehouse.objects.create(name="CD Recife", state="PE")
    with pytest.raises(DomainError):
        disposals.add_asset(_sale(other, customer, admin), available(), user=admin)


# --- Picking and shipping ----------------------------------------------------------------------


def test_pick_against_the_list_and_ship(
    available, shipping, places, warehouse, customer, storekeeper, admin
):
    first, second, stranger = available(), available(), available()
    appointment = Appointment.objects.create(
        year=2026,
        sequence=1,
        kind=AppointmentKind.SHIPPING,
        warehouse=warehouse,
        starts_at="2026-11-25T10:00:00Z",
        ends_at="2026-11-25T11:00:00Z",
        created_by=admin,
    )
    sale = _sale(warehouse, customer, admin, appointment=appointment)
    disposals.add_asset(sale, first, user=admin, unit_value=Decimal("1000"))
    disposals.add_asset(sale, second, user=admin, unit_value=Decimal("800.50"))
    assert disposals.totals(sale) == {"assets": 2, "accessories": 0, "total_value": "1800.50"}

    # Not a shipping area; not on the list
    with pytest.raises(DomainError):
        disposals.pick_asset(sale, first, shipping_location=places["shelf"], user=storekeeper)
    with pytest.raises(DomainError) as error:
        disposals.pick_asset(sale, stranger, shipping_location=shipping, user=storekeeper)
    assert error.value.field == "code"

    disposals.pick_asset(sale, first, shipping_location=shipping, user=storekeeper)
    sale.refresh_from_db()
    assert sale.status == DisposalStatus.PICKING
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.IN_PROGRESS
    first.refresh_from_db()
    assert first.current_location == shipping
    assert first.events.filter(kind=EventKind.PICKING, document_ref=sale.ref).exists()
    with pytest.raises(DomainError):  # read twice
        disposals.pick_asset(sale, first, shipping_location=shipping, user=storekeeper)

    # Divergence (one not picked) blocks the shipping
    _ready(sale, storekeeper)
    with pytest.raises(DomainError) as error:
        disposals.ship(sale, user=storekeeper)
    assert "not picked" in str(error.value.message)

    disposals.pick_asset(sale, second, shipping_location=shipping, user=storekeeper)
    disposals.ship(sale, user=storekeeper)
    sale.refresh_from_db()
    assert sale.status == DisposalStatus.SHIPPED
    for asset in (first, second):
        asset.refresh_from_db()
        assert asset.status == AssetStatus.WRITTEN_OFF
        assert asset.events.filter(kind=EventKind.SHIPPING).exists()
        assert _trail_matches(asset)
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.DONE
    # Closed: nothing else changes
    with pytest.raises(DomainError):
        disposals.cancel(sale, user=admin, reason="Too late")


def test_shipping_needs_the_document(available, shipping, warehouse, customer, storekeeper, admin):
    asset = available()
    sale = _sale(warehouse, customer, admin)
    disposals.add_asset(sale, asset, user=admin)
    disposals.pick_asset(sale, asset, shipping_location=shipping, user=storekeeper)
    found = " ".join(str(p) for p in disposals.problems(sale))
    assert "document's number" in found and "Attach the shipping document" in found
    with pytest.raises(DomainError):
        disposals.ship(sale, user=storekeeper)


def test_a_dispute_after_reserving_blocks_the_shipping(
    available, shipping, warehouse, customer, storekeeper, admin
):
    asset = available()
    sale = _sale(warehouse, customer, admin)
    disposals.add_asset(sale, asset, user=admin)
    disposals.pick_asset(sale, asset, shipping_location=shipping, user=storekeeper)
    _ready(sale, storekeeper)
    Asset.objects.filter(pk=asset.pk).update(held_for_dispute=True)
    with pytest.raises(DomainError) as error:
        disposals.ship(sale, user=storekeeper)
    assert "dispute" in str(error.value.message)


def test_discard_needs_the_certificate_rn23(
    scrap, shipping, warehouse, recycler, storekeeper, admin
):
    discard = disposals.create(
        kind=DisposalKind.DISCARD, warehouse=warehouse, user=admin, discard_provider=recycler
    )
    disposals.add_asset(discard, scrap, user=admin)
    disposals.pick_asset(discard, scrap, shipping_location=shipping, user=storekeeper)
    _ready(discard, storekeeper)
    with pytest.raises(DomainError) as error:
        disposals.ship(discard, user=storekeeper)
    assert "certificate" in str(error.value.message)
    disposals.add_file(
        discard, kind=DisposalFileKind.CERTIFICATE, upload=_file("cert.pdf"), user=admin
    )
    disposals.ship(discard, user=storekeeper)
    scrap.refresh_from_db()
    assert scrap.status == AssetStatus.WRITTEN_OFF
    # Kept once shipped
    with pytest.raises(DomainError):
        disposals.remove_file(discard.files.get(kind=DisposalFileKind.CERTIFICATE))


def test_certificate_only_in_discards(warehouse, customer, admin):
    with pytest.raises(DomainError):
        disposals.add_file(
            _sale(warehouse, customer, admin),
            kind=DisposalFileKind.CERTIFICATE,
            upload=_file(),
            user=admin,
        )


# --- Cancelling --------------------------------------------------------------------------------


def test_cancel_gives_everything_back(
    available, scrap, shipping, places, warehouse, customer, cables, storekeeper, admin, recycler
):
    picked, reserved = available(), available()
    services.add_accessories(cables, 10, user=admin, location=places["shelf"])
    sale = _sale(warehouse, customer, admin)
    disposals.add_asset(sale, picked, user=admin)
    disposals.add_asset(sale, reserved, user=admin)
    line = disposals.add_accessory(sale, cables, 4, user=admin)
    disposals.pick_asset(sale, picked, shipping_location=shipping, user=storekeeper)
    disposals.pick_accessory(sale, line, 3, user=storekeeper, location=places["shelf"])
    balance = AccessoryBalance.objects.get(asset_model=cables, location=places["shelf"])
    assert balance.quantity == 7

    with pytest.raises(DomainError):
        disposals.cancel(sale, user=admin, reason=" ")
    disposals.cancel(sale, user=admin, reason="Buyer gave up")
    sale.refresh_from_db()
    assert sale.status == DisposalStatus.CANCELLED
    for asset in (picked, reserved):
        asset.refresh_from_db()
        assert asset.status == AssetStatus.AVAILABLE
        assert asset.current_location == places["shelf"]
        assert _trail_matches(asset)
    balance.refresh_from_db()
    assert balance.quantity == 10

    # A scrap asset picked for a discard goes back to the scrap area, still scrap
    discard = disposals.create(
        kind=DisposalKind.DISCARD, warehouse=warehouse, user=admin, discard_provider=recycler
    )
    disposals.add_asset(discard, scrap, user=admin)
    disposals.pick_asset(discard, scrap, shipping_location=shipping, user=storekeeper)
    disposals.cancel(discard, user=admin, reason="Provider late")
    scrap.refresh_from_db()
    assert (scrap.status, scrap.current_location) == (AssetStatus.SCRAP, places["scrap"])


def test_disposal_events_are_not_reversed_by_hand(available, warehouse, customer, admin):
    asset = available()
    disposals.add_asset(_sale(warehouse, customer, admin), asset, user=admin)
    event = asset.events.order_by("-at", "-id").first()
    with pytest.raises(DomainError):
        services.reverse_event(event, user=admin, reason="Oops")


# --- Accessories -------------------------------------------------------------------------------


def test_accessories_by_quantity(places, shipping, warehouse, customer, cables, storekeeper, admin):
    services.add_accessories(cables, 5, user=admin, location=places["shelf"])
    first = _sale(warehouse, customer, admin)
    line = disposals.add_accessory(first, cables, 3, user=admin, unit_value=Decimal("10"))
    # Only 2 left for another disposal
    with pytest.raises(DomainError) as error:
        disposals.add_accessory(_sale(warehouse, customer, admin), cables, 3, user=admin)
    assert "2" in str(error.value.message)
    # Scrap accessories only in discards
    with pytest.raises(DomainError):
        disposals.add_accessory(first, cables, 1, user=admin, condition="scrap")
    with pytest.raises(DomainError):
        disposals.pick_accessory(first, line, 4, user=storekeeper, location=places["shelf"])
    disposals.pick_accessory(first, line, 2, user=storekeeper, location=places["shelf"])
    disposals.pick_accessory(first, line, 1, user=storekeeper, location=places["shelf"])
    _ready(first, storekeeper)
    disposals.ship(first, user=storekeeper)
    assert AccessoryBalance.objects.get(asset_model=cables).quantity == 2
    assert MovementEvent.objects.filter(
        kind=EventKind.SHIPPING, accessory_model=cables, quantity=3
    ).exists()
    assert disposals.totals(first)["total_value"] == "30.00"


# --- Parts -------------------------------------------------------------------------------------


def test_taking_scrap_apart_records_a_parts_disposal(scrap, cables, admin):
    inspection.disassemble(scrap, user=admin, parts=[{"asset_model": cables, "quantity": 2}])
    disposal = Disposal.objects.get(kind=DisposalKind.PARTS)
    assert disposal.status == DisposalStatus.SHIPPED
    assert disposal.items.get().asset == scrap


# --- Stock query -------------------------------------------------------------------------------


def test_stock_query_groups_and_units(client, available, scrap, warehouse, customer, nobody):
    available()
    available()
    Asset.objects.update(condition_grade="B1C")
    client_for(client, nobody)
    groups = client.get(f"{API}/stock/").json()
    assert len(groups) == 1
    assert groups[0]["units"] == 2 and groups[0]["grade"] == "B1C"
    assert groups[0]["asset_class_name"] == "Notebook"
    every = client.get(f"{API}/stock/?status=all").json()
    assert sum(g["units"] for g in every) == 3
    assert client.get(f"{API}/stock/?min_days=5").json() == []
    units = client.get(f"{API}/stock/assets/?grade=b1c").json()
    assert units["count"] == 2
    assert units["results"][0]["days_in_stock"] == 0
    assert units["results"][0]["report"] is None


# --- API and permissions ---------------------------------------------------------------------


def test_api_flow_and_roles(
    client, available, shipping, warehouse, customer, commercial, storekeeper, nobody
):
    asset = available()
    client_for(client, nobody)
    refused = client.post(
        f"{API}/disposals/",
        {"kind": "lessee_sale", "warehouse": warehouse.id, "customer": customer.id},
        content_type="application/json",
    )
    assert refused.status_code == 403

    client_for(client, commercial)
    created = client.post(
        f"{API}/disposals/",
        {
            "kind": "lessee_sale",
            "warehouse": warehouse.id,
            "customer": customer.id,
            "keywords": ["Fleet"],
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.json()
    url = f"{API}/disposals/{created.json()['id']}/"
    data = client.post(
        f"{url}items/",
        {"codes": [asset.horizon_id], "unit_value": "900"},
        content_type="application/json",
    ).json()
    assert data["items"][0]["asset_detail"]["horizon_id"] == asset.horizon_id
    assert data["totals"]["total_value"] == "900.00"
    assert any("not picked" in p for p in data["problems"])
    # Commercial does not pick
    assert (
        client.post(
            f"{url}pick/",
            {"code": asset.horizon_id, "shipping_location": shipping.code},
            content_type="application/json",
        ).status_code
        == 403
    )
    client.patch(url, {"document_number": "NF 9"}, content_type="application/json")
    client.post(f"{url}files/", {"kind": "document", "file": _file()})
    client_for(client, storekeeper)
    missing = client.post(
        f"{url}pick/", {"code": asset.horizon_id}, content_type="application/json"
    )
    assert missing.json()["field"] == "shipping_location"
    picked = client.post(
        f"{url}pick/",
        {"code": asset.horizon_id, "shipping_location": shipping.code},
        content_type="application/json",
    ).json()
    assert picked["status"] == "picking" and picked["items"][0]["picked"]
    assert client.patch(url, {"notes": "x"}, content_type="application/json").status_code == 403
    shipped = client.post(f"{url}ship/").json()
    assert shipped["status"] == "shipped"
    client_for(client, commercial)
    listed = client.get(f"{API}/disposals/?search={created.json()['code']}").json()
    assert listed["count"] == 1 and listed["results"][0]["items_count"] == 1
