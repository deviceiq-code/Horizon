"""Receiving: appointments, blind count (RN-17), triage of units and accessories (RN-05,
RN-06), reconciliation, occurrences and closing (RN-18)."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from catalogs.models import AssetModel, Manufacturer, Tracking
from service_providers.models import ServiceKind, ServiceProvider

from . import receiving, services
from .conftest import client_for
from .models import (
    AccessoryBalance,
    AccessoryCondition,
    Appointment,
    AppointmentStatus,
    Asset,
    Container,
    LotStatus,
    Occurrence,
    OccurrenceStatus,
)
from .states import AreaType, AssetStatus, DomainError

API = "/api/inventory"
PHOTO = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _post(client, url, data):
    return client.post(url, data, content_type="application/json")


def _photo():
    return SimpleUploadedFile("asset.png", PHOTO, content_type="image/png")


@pytest.fixture
def cable(notebook_class):
    acme = Manufacturer.objects.create(name="Acme")
    return AssetModel.objects.create(
        manufacturer=acme,
        name="USB-C Cable",
        asset_class=notebook_class,
        tracking=Tracking.QUANTITY,
    )


@pytest.fixture
def appointment(analyst, warehouse, customer, notebook, cable):
    start = timezone.now() + timedelta(hours=1)
    appointment = receiving.create_with_code(
        Appointment,
        kind="receiving",
        warehouse=warehouse,
        customer=customer,
        starts_at=start,
        ends_at=start + timedelta(hours=2),
        created_by=analyst,
    )
    appointment.expected_items.create(asset_model=notebook, serial="ABC0001")
    appointment.expected_items.create(asset_model=notebook, serial="ABC0002")
    appointment.expected_items.create(asset_model=cable, quantity=10)
    return appointment


@pytest.fixture
def lot(appointment, places, receiver):
    return receiving.open_lot(
        warehouse=appointment.warehouse,
        appointment=appointment,
        dock=places["dock"],
        user=receiver,
    )


# --- Appointments ------------------------------------------------------------------------------


def test_analyst_schedules_a_receiving_with_its_expected_list(
    client, analyst, warehouse, customer, notebook
):
    client_for(client, analyst)
    start = timezone.now() + timedelta(days=1)
    payload = {
        "kind": "receiving",
        "warehouse": warehouse.id,
        "customer": customer.id,
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=2)).isoformat(),
        "vehicle_plate": "abc 1d23",
        "expected_items": [
            {"asset_model": notebook.id, "serial": " abc 0001 "},
            {"asset_model": notebook.id, "quantity": 3},
        ],
    }
    response = _post(client, f"{API}/appointments/", payload)
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["code"].startswith("APT-") and data["status"] == "scheduled"
    assert data["vehicle_plate"] == "ABC1D23"
    assert [(i["serial"], i["quantity"]) for i in data["expected_items"]] == [
        ("ABC0001", 1),
        ("", 3),
    ]

    # Overlaps are only warned about
    second = _post(client, f"{API}/appointments/", {**payload, "expected_items": []})
    assert second.status_code == 201
    assert second.json()["conflicts"] == [data["code"]]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"customer": None}, "customer"),
        ({"expected_items": [{"asset_model": 0, "serial": "S", "quantity": 2}]}, "expected_items"),
    ],
)
def test_appointment_validation(client, analyst, warehouse, customer, notebook, overrides, field):
    client_for(client, analyst)
    start = timezone.now()
    payload = {
        "kind": "receiving",
        "warehouse": warehouse.id,
        "customer": customer.id,
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
        **overrides,
    }
    if field == "expected_items":
        payload["expected_items"][0]["asset_model"] = notebook.id
    response = _post(client, f"{API}/appointments/", payload)
    assert response.status_code == 400
    assert field in response.json()


def test_carrier_must_offer_transport(client, analyst, appointment):
    storage = ServiceProvider.objects.create(
        name="Armazéns Ltda", tax_id="12ABC34501DE35", services=[ServiceKind.WAREHOUSING]
    )
    trucks = ServiceProvider.objects.create(
        name="Fretes Ltda", tax_id="11444777000161", services=[ServiceKind.TRANSPORT]
    )
    client_for(client, analyst)
    url = f"{API}/appointments/{appointment.id}/"
    response = client.patch(url, {"carrier": storage.id}, content_type="application/json")
    assert "carrier" in response.json()
    response = client.patch(url, {"carrier": trucks.id}, content_type="application/json")
    assert response.json()["carrier_detail"]["name"] == "Fretes Ltda"


def test_only_schedulers_write_appointments(client, receiver, appointment):
    client_for(client, receiver)
    assert client.get(f"{API}/appointments/").status_code == 200
    response = client.patch(
        f"{API}/appointments/{appointment.id}/", {"notes": "x"}, content_type="application/json"
    )
    assert response.status_code == 403


def test_appointment_status(client, analyst, appointment):
    client_for(client, analyst)
    url = f"{API}/appointments/{appointment.id}/status/"
    assert _post(client, url, {"status": "confirmed"}).json()["status"] == "confirmed"
    # A receiving starts with its lot, not by hand
    assert _post(client, url, {"status": "in_progress"}).status_code == 400
    assert _post(client, url, {"status": "cancelled"}).json()["status"] == "cancelled"
    assert _post(client, url, {"status": "scheduled"}).json()["status"] == "scheduled"


def test_parse_pasted_expected_list(client, analyst, notebook, cable):
    client_for(client, analyst)
    text = (
        "Modelo\tSérie\tQtd\n"
        "Dell Latitude 5440\tS1\t\n"
        "USB-C Cable\t\t10\n"
        "Unknown\t\t1\n"
        "Latitude 5440\tS2\t3"
    )
    rows = _post(client, f"{API}/appointments/parse-expected/", {"text": text}).json()["rows"]
    assert [(r["asset_model"], r["serial"], r["quantity"], bool(r["errors"])) for r in rows] == [
        (notebook.id, "S1", 1, False),
        (cable.id, "", 10, False),
        (None, "", 1, True),
        (notebook.id, "S2", 3, True),  # the model alone is found; a serial is one unit
    ]


# --- Blind count (RN-17) ---------------------------------------------------------------------


def test_receivers_never_see_the_expected_list(client, receiver, commercial, analyst, lot):
    client_for(client, receiver)
    appointment = client.get(f"{API}/appointments/{lot.appointment_id}/").json()
    assert "expected_items" not in appointment
    assert client.get(f"{API}/lots/{lot.id}/expected/").status_code == 403
    assert "expected" not in str(client.get(f"{API}/lots/{lot.id}/").json()).lower()
    for user in (commercial, analyst):
        client_for(client, user)
        assert len(client.get(f"{API}/lots/{lot.id}/expected/").json()) == 3


# --- Lots and triage -------------------------------------------------------------------------


def test_open_lot_from_an_appointment(client, receiver, appointment, places):
    client_for(client, receiver)
    response = _post(
        client,
        f"{API}/lots/",
        {
            "appointment": appointment.id,
            "dock_code": places["dock"].code,
            "fiscal_document_number": " 123 ",
        },
    )
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["code"].startswith("LOT-")
    assert data["customer"] == appointment.customer_id
    assert data["is_scheduled"] is True
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.IN_PROGRESS
    # The same appointment does not open twice
    again = _post(
        client, f"{API}/lots/", {"appointment": appointment.id, "dock_code": places["dock"].code}
    )
    assert again.status_code == 400


def test_open_unscheduled_lot_needs_a_dock(client, receiver, warehouse, customer, places):
    client_for(client, receiver)
    response = _post(
        client,
        f"{API}/lots/",
        {"warehouse": warehouse.id, "customer": customer.id, "dock_code": places["stock"].code},
    )
    assert response.status_code == 400
    assert response.json()["field"] == "dock"
    response = _post(
        client,
        f"{API}/lots/",
        {"warehouse": warehouse.id, "customer": customer.id, "dock_code": places["dock"].code},
    )
    assert response.status_code == 201
    assert response.json()["is_scheduled"] is False


def test_triage_a_unit(client, receiver, lot, notebook):
    client_for(client, receiver)
    response = client.post(
        f"{API}/lots/{lot.id}/units/", {"asset_model": notebook.id, "serial": "abc0001"}
    )
    assert response.status_code == 201, response.json()
    asset = Asset.objects.get(pk=response.json()["id"])
    assert (asset.lot, asset.customer, asset.status) == (lot, lot.customer, AssetStatus.IN_TRIAGE)
    assert asset.current_location == lot.dock
    assert asset.events.get().document_ref == f"lot:{lot.id}"
    # RN-05: the same serial twice
    again = client.post(
        f"{API}/lots/{lot.id}/units/", {"asset_model": notebook.id, "serial": "ABC0001"}
    )
    assert again.status_code == 400
    assert again.json()["field"] == "serial"


def test_without_serial_a_photo_is_required(client, receiver, lot, notebook):
    client_for(client, receiver)
    url = f"{API}/lots/{lot.id}/units/"
    response = client.post(url, {"asset_model": notebook.id, "no_serial_reason": "needs_power_on"})
    assert response.json()["field"] == "photo"
    response = client.post(
        url, {"asset_model": notebook.id, "no_serial_reason": "needs_power_on", "photo": _photo()}
    )
    assert response.status_code == 201, response.json()
    asset = Asset.objects.get(pk=response.json()["id"])
    assert asset.serial_status == "pending"
    assert asset.attachments.get().kind == "no_serial_photo"


def test_triage_accessories_and_balances_never_negative_rn06(
    client, receiver, admin, lot, cable, places
):
    box = services.create_container(kind="box", location=places["dock"], user=admin)
    client_for(client, receiver)
    url = f"{API}/lots/{lot.id}/accessories/"
    response = _post(
        client,
        url,
        {"asset_model": cable.id, "quantity": 8, "container_code": box.code, "damaged_quantity": 2,
         "scrap_code": places["scrap"].code},
    )  # fmt: skip
    assert response.status_code == 201, response.json()
    good = AccessoryBalance.objects.get(container=box, condition=AccessoryCondition.GOOD)
    scrap = AccessoryBalance.objects.get(
        location=places["scrap"], condition=AccessoryCondition.SCRAP
    )
    assert (good.quantity, scrap.quantity) == (8, 2)
    assert len(response.json()["accessories"]) == 2
    # Damaged ones only to a scrap area
    bad = _post(
        client,
        url,
        {"asset_model": cable.id, "damaged_quantity": 1, "scrap_code": places["stock"].code},
    )
    assert bad.json()["field"] == "scrap_destination"
    # Never below zero
    with pytest.raises(DomainError):
        services.remove_accessories(cable, 9, user=admin, container=box)
    services.remove_accessories(cable, 8, user=admin, container=box)
    good.refresh_from_db()
    assert good.quantity == 0


def test_unit_models_are_not_counted_as_accessories(client, receiver, lot, notebook):
    client_for(client, receiver)
    response = _post(
        client, f"{API}/lots/{lot.id}/accessories/", {"asset_model": notebook.id, "quantity": 1}
    )
    assert response.json()["field"] == "asset_model"


# --- Reconciliation, occurrences and closing (RN-18) -------------------------------------------


def _triage(lot, user, model, serial):
    return receiving.triage_unit(lot, user=user, asset_model=model, serial=serial)


def test_reconcile_and_close_with_divergences_handled(
    client, receiver, supervisor, lot, notebook, cable, places
):
    _triage(lot, receiver, notebook, "ABC0001")
    _triage(lot, receiver, notebook, "ABC0009")  # instead of ABC0002
    receiving.triage_accessories(lot, user=receiver, asset_model=cable, quantity=10)

    client_for(client, receiver)
    response = _post(client, f"{API}/lots/{lot.id}/close/", {})
    assert response.status_code == 400  # RN-18
    assert response.json()["field"] == "occurrences"
    occurrence = Occurrence.objects.get(lot=lot)  # kept although closing was refused
    assert (occurrence.kind, occurrence.expected_serial, occurrence.received_serial) == (
        "serial_mismatch",
        "ABC0002",
        "ABC0009",
    )
    lot.refresh_from_db()
    assert lot.status == LotStatus.RECONCILING

    # Reconciling again does not duplicate
    _post(client, f"{API}/lots/{lot.id}/reconcile/", {})
    assert Occurrence.objects.filter(lot=lot).count() == 1

    # Accepting is for supervisors
    assert (
        _post(
            client, f"{API}/occurrences/{occurrence.id}/accept/", {"resolution": "ok"}
        ).status_code
        == 403
    )
    client_for(client, supervisor)
    assert (
        _post(client, f"{API}/occurrences/{occurrence.id}/accept/", {"resolution": ""}).status_code
        == 400
    )
    response = _post(
        client,
        f"{API}/occurrences/{occurrence.id}/accept/",
        {"resolution": "Customer confirmed the swap."},
    )
    assert response.json()["status"] == "accepted"

    client_for(client, receiver)
    response = _post(client, f"{API}/lots/{lot.id}/close/", {})
    assert response.status_code == 200, response.json()
    assert response.json()["status"] == "closed"
    # Not recreated by the last reconciliation
    assert Occurrence.objects.filter(lot=lot).count() == 1
    assert set(lot.assets.values_list("status", flat=True)) == {AssetStatus.AWAITING_INSPECTION}
    lot.appointment.refresh_from_db()
    assert lot.appointment.status == AppointmentStatus.DONE
    # A closed lot takes nothing more
    response = client.post(
        f"{API}/lots/{lot.id}/units/", {"asset_model": notebook.id, "serial": "ABC0003"}
    )
    assert response.status_code == 400


def test_manual_occurrence_resolved(client, receiver, lot):
    client_for(client, receiver)
    response = _post(
        client,
        f"{API}/occurrences/",
        {"lot": lot.id, "kind": "transport_damage", "description": "Box crushed", "quantity": 1},
    )
    assert response.status_code == 201, response.json()
    occurrence_id = response.json()["id"]
    assert (
        _post(client, f"{API}/occurrences/{occurrence_id}/resolve/", {"resolution": ""}).status_code
        == 400
    )
    resolved = _post(
        client, f"{API}/occurrences/{occurrence_id}/resolve/", {"resolution": "Carrier notified."}
    )
    assert resolved.json()["status"] == "resolved"
    assert Occurrence.objects.get(pk=occurrence_id).status == OccurrenceStatus.RESOLVED


def test_unscheduled_lot_closes_without_reconciliation(
    receiver, warehouse, customer, places, notebook
):
    lot = receiving.open_lot(
        warehouse=warehouse, customer=customer, dock=places["dock"], user=receiver
    )
    _triage(lot, receiver, notebook, "ABC0001")
    closed = receiving.close_lot(lot, user=receiver)
    assert closed.status == LotStatus.CLOSED
    assert not closed.occurrences.exists()


def test_closed_lot_assets_go_to_the_inspection_queue_by_container(
    client, receiver, storekeeper, admin, lot, notebook, places
):
    box = services.create_container(kind="cage", location=places["dock"], user=admin)
    for serial in ("ABC0001", "ABC0002"):
        receiving.triage_unit(
            lot, user=receiver, asset_model=notebook, serial=serial, container=box
        )
    receiving.triage_accessories(
        lot, user=receiver, asset_model=AssetModel.objects.get(name="USB-C Cable"), quantity=10
    )
    receiving.close_lot(lot, user=receiver)
    client_for(client, storekeeper)
    response = _post(
        client,
        f"{API}/movements/",
        {"object_code": box.code, "destination_code": places["queue"].code},
    )
    assert response.status_code == 201, response.json()
    assert set(Asset.objects.filter(lot=lot).values_list("current_location", flat=True)) == {
        places["queue"].id
    }
    assert Container.objects.get(pk=box.pk).current_location == places["queue"]


def test_attachments(client, receiver, lot):
    client_for(client, receiver)
    url = f"{API}/lots/{lot.id}/attachments/"
    pdf = SimpleUploadedFile("nf.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    response = client.post(url, {"file": pdf, "kind": "fiscal_document"})
    assert response.status_code == 200, response.json()
    attachment = response.json()[0]
    assert attachment["kind"] == "fiscal_document"
    # Photos only for photo kinds
    bad = client.post(url, {"file": SimpleUploadedFile("x.pdf", b"%PDF"), "kind": "damage_photo"})
    assert bad.json()["field"] == "file"
    download = client.get(f"{url}{attachment['id']}/download/")
    assert download.status_code == 200
    assert client.delete(f"{url}{attachment['id']}/").status_code == 204


def test_accessory_balances_list(client, storekeeper, receiver, lot, cable, places):
    receiving.triage_accessories(lot, user=receiver, asset_model=cable, quantity=4)
    client_for(client, storekeeper)
    rows = client.get(f"{API}/accessory-balances/").json()["results"]
    assert [
        (r["asset_model_label"], r["quantity"], r["location_detail"]["code"]) for r in rows
    ] == [("Acme USB-C Cable", 4, places["dock"].code)]
    assert places["dock"].area_type == AreaType.DOCK
