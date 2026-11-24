"""Inspection: reports, grade, photos, findings and the penalty table, data erasure,
approval and new versions, part harvesting (RN-03, RN-04, RN-09 to RN-13)."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from catalogs.models import AssetModel, Manufacturer, Tracking
from users.models import INSPECTION_TECHNICIAN

from . import inspection, receiving
from .conftest import client_for, user_with_roles
from .models import (
    Asset,
    ErasureTool,
    InspectionReport,
    LotErasureTool,
    PenaltyRate,
    ReportStatus,
)
from .states import AssetStatus, DomainError

API = "/api/inventory"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _png(name="front.png"):
    return SimpleUploadedFile(name, PNG, content_type="image/png")


def _pdf():
    return SimpleUploadedFile("cert.pdf", b"%PDF-1.4 erased", content_type="application/pdf")


def _post(client, url, data):
    return client.post(url, data, content_type="application/json")


@pytest.fixture
def technician(db):
    return user_with_roles("technician", INSPECTION_TECHNICIAN)


@pytest.fixture
def setup(notebook, notebook_class, places, receiver, supervisor, warehouse, customer):
    """A notebook (data storage; kit and test script; front photo required) waiting for
    inspection, its lot's erasure tool defined and a penalty table."""
    notebook.kit_checklist = [
        {"item": "Charger", "essential": False},
        {"item": "Battery", "essential": True},
    ]
    notebook.test_script = ["Boots", "Keyboard"]
    notebook.save()
    notebook_class.required_photo_kinds = ["front"]
    notebook_class.save()
    lot = receiving.open_lot(
        warehouse=warehouse, customer=customer, dock=places["dock"], user=receiver
    )
    asset = receiving.triage_unit(lot, user=receiver, asset_model=notebook, serial="ABC0001")
    receiving.close_lot(lot, user=receiver)
    tool = ErasureTool.objects.create(name="Blancco", version="7.1", methods=["purge"])
    tool.asset_classes.add(notebook_class)
    LotErasureTool.objects.create(
        lot=lot, asset_class=notebook_class, tool=tool, method="purge", defined_by=supervisor
    )
    for kind, value in (
        ("missing_item", "150.00"),
        ("heavy_cleaning", "80.00"),
        ("access_block", "500.00"),
    ):
        PenaltyRate.objects.create(
            asset_class=notebook_class,
            finding_kind=kind,
            value=Decimal(value),
            valid_from=date(2026, 1, 1),
        )
    asset.refresh_from_db()
    return {"asset": asset, "lot": lot, "tool": tool}


def _start(client, technician, setup, places):
    client_for(client, technician)
    response = _post(
        client,
        f"{API}/inspections/start/",
        {"asset_code": setup["asset"].horizon_id, "bench_code": places["bench"].code},
    )
    assert response.status_code == 200, response.json()
    return response.json()


def _complete(client, report_id, technician_client=True):
    """Fill in everything a submission needs (no findings)."""
    url = f"{API}/inspections/{report_id}/"
    client.post(f"{url}photos/", {"kind": "front", "file": _png()})
    client.post(f"{url}certificates/", {"result": "success", "disk_serial": "S1", "file": _pdf()})
    response = client.patch(
        url,
        {
            "checklist_done": True,
            "missing_items": [],
            "test_results": {"Boots": "pass", "Keyboard": "pass"},
            "conservation": "B",
            "functioning": "1",
            "completeness": "C",
        },
        content_type="application/json",
    )
    assert response.status_code == 200, response.json()
    return response.json()


# --- Starting ----------------------------------------------------------------------------------


def test_start_at_a_bench(client, technician, setup, places):
    data = _start(client, technician, setup, places)
    asset = Asset.objects.get(pk=setup["asset"].pk)
    assert (asset.status, asset.current_location) == (AssetStatus.IN_INSPECTION, places["bench"])
    assert (data["version"], data["status"]) == (1, "draft")
    assert data["kit_checklist"][1] == {"item": "Battery", "essential": True}
    assert data["lot_tool"]["tool_label"] == "Blancco 7.1"
    # Read again: the same report is resumed
    again = _start(client, technician, setup, places)
    assert again["id"] == data["id"]


def test_start_needs_a_bench(client, technician, setup, places):
    client_for(client, technician)
    response = _post(
        client,
        f"{API}/inspections/start/",
        {"asset_code": setup["asset"].horizon_id, "bench_code": places["stock"].code},
    )
    assert response.json()["field"] == "bench"


# --- Draft: grade suggestions, automatic findings, values ----------------------------------------


def test_suggestions_and_automatic_findings(client, technician, setup, places):
    report = _start(client, technician, setup, places)
    url = f"{API}/inspections/{report['id']}/"
    data = client.patch(
        url,
        {
            "checklist_done": True,
            "missing_items": ["battery"],
            "test_results": {"Boots": "pass", "Keyboard": "fail"},
            "cleaning": "heavy",
        },
        content_type="application/json",
    ).json()
    assert data["missing_items"] == ["Battery"]
    assert data["suggestions"]["functioning"] == "2"
    assert data["suggestions"]["completeness"] == "I"
    assert sorted((f["kind"], f["item"], f["value"]) for f in data["findings"]) == [
        ("heavy_cleaning", "", "80.00"),
        ("missing_item", "Battery", "150.00"),
    ]
    # Back to standard cleaning, nothing missing: the automatic findings go away
    data = client.patch(
        url, {"cleaning": "standard", "missing_items": []}, content_type="application/json"
    ).json()
    assert data["findings"] == []
    # Only kit items and script checks are accepted
    bad = client.patch(url, {"missing_items": ["Mouse"]}, content_type="application/json")
    assert "missing_items" in bad.json()


def test_complete_pending_serial(client, technician, setup, places, receiver, notebook):
    asset = setup["asset"]
    Asset.objects.filter(pk=asset.pk).update(
        serial="", serial_status="pending", no_serial_reason="needs_power_on"
    )
    report = _start(client, technician, setup, places)
    url = f"{API}/inspections/{report['id']}/serial/"
    assert _post(client, url, {"serial": "bad"}).json()["field"] == "serial"  # pattern
    data = _post(client, url, {"serial": "abc0002"}).json()
    assert data["asset_detail"]["serial"] == "ABC0002"
    assert data["asset_detail"]["serial_status"] == "captured"


# --- Submitting and approving ----------------------------------------------------------------


def test_submit_lists_what_is_missing(client, technician, setup, places):
    report = _start(client, technician, setup, places)
    response = _post(client, f"{API}/inspections/{report['id']}/submit/", {})
    assert response.status_code == 400
    message = response.json()["detail"]
    for words in ("photos", "kit", "test script", "conservation", "Erase the data"):
        assert words in message


def test_approval_by_another_user_rn10(client, technician, supervisor, setup, places):
    report = _start(client, technician, setup, places)
    _complete(client, report["id"])
    data = _post(client, f"{API}/inspections/{report['id']}/submit/", {}).json()
    assert (data["status"], data["grade"], data["recommended_destination"]) == (
        "awaiting_approval",
        "B1C",
        "available",
    )
    # A technician does not approve
    assert _post(client, f"{API}/inspections/{report['id']}/approve/", {}).status_code == 403
    # Nor does the supervisor who prepared it
    own = InspectionReport.objects.get(pk=report["id"])
    InspectionReport.objects.filter(pk=own.pk).update(technician=supervisor)
    client_for(client, supervisor)
    refused = _post(client, f"{API}/inspections/{report['id']}/approve/", {})
    assert refused.json()["field"] == "approved_by"
    InspectionReport.objects.filter(pk=own.pk).update(technician=technician)
    data = _post(client, f"{API}/inspections/{report['id']}/approve/", {}).json()
    assert (data["status"], data["is_current"]) == ("approved", True)
    asset = Asset.objects.get(pk=setup["asset"].pk)
    assert (asset.status, asset.condition_grade) == (AssetStatus.AVAILABLE, "B1C")


def test_findings_without_a_rate_block_approval_rn11(client, technician, supervisor, setup, places):
    PenaltyRate.objects.filter(finding_kind="access_block").delete()
    report = _start(client, technician, setup, places)
    _complete(client, report["id"])
    data = _post(
        client,
        f"{API}/inspections/{report['id']}/findings/",
        {"kind": "access_block", "block_type": "mdm", "description": "MDM enrolled"},
    ).json()
    assert data["findings"][0]["value"] is None
    data = _post(client, f"{API}/inspections/{report['id']}/submit/", {}).json()
    assert data["recommended_destination"] == "blocked"
    client_for(client, supervisor)
    refused = _post(client, f"{API}/inspections/{report['id']}/approve/", {})
    assert refused.json()["field"] == "findings"
    # The supervisor values it (with a justification) and approves
    finding_id = data["findings"][0]["id"]
    url = f"{API}/inspections/{report['id']}/findings/{finding_id}/"
    assert client.patch(url, {"value": "300"}, content_type="application/json").status_code == 400
    response = client.patch(
        url,
        {"value": "300", "value_justification": "Agreed with the customer"},
        content_type="application/json",
    )
    assert response.json()["findings"][0]["value"] == "300.00"
    data = _post(client, f"{API}/inspections/{report['id']}/approve/", {}).json()
    assert data["status"] == "approved"
    assert Asset.objects.get(pk=setup["asset"].pk).status == AssetStatus.BLOCKED


def test_data_must_be_erased_before_available_rn12(technician, supervisor, setup, places):
    report = inspection.start_inspection(setup["asset"], bench=places["bench"], user=technician)
    with pytest.raises(DomainError) as exc:
        inspection.submit(report, user=technician)
    assert "Erase the data" in exc.value.message


def test_erasure_uses_the_lots_tool_rn04(client, technician, setup, places):
    LotErasureTool.objects.all().delete()
    report = _start(client, technician, setup, places)
    response = client.post(
        f"{API}/inspections/{report['id']}/certificates/", {"result": "success", "file": _pdf()}
    )
    assert response.json()["field"] == "tool"


def test_failed_erasure_removes_the_disk_rn13(client, technician, setup, places, notebook_class):
    disk_model = AssetModel.objects.create(
        manufacturer=Manufacturer.objects.create(name="Samsung"),
        name="SSD 512 GB",
        asset_class=notebook_class,
    )
    report = _start(client, technician, setup, places)
    url = f"{API}/inspections/{report['id']}/certificates/"
    assert client.post(url, {"result": "failure"}).json()["field"] == "disk_model"
    data = client.post(
        url, {"result": "failure", "disk_serial": "d1", "disk_model": disk_model.id}
    ).json()
    certificate = data["erasures"][0]
    assert (certificate["result"], certificate["tool_label"], certificate["method"]) == (
        "failure",
        "Blancco 7.1",
        "purge",
    )
    disk = Asset.objects.get(pk=certificate["removed_disk"])
    assert (disk.parent_asset_id, disk.status, disk.serial) == (
        setup["asset"].pk,
        AssetStatus.SCRAP,
        "D1",
    )
    assert inspection.storage_cleared(Asset.objects.get(pk=setup["asset"].pk))


def test_approved_report_never_changes_new_version_rn09(
    client, technician, supervisor, setup, places
):
    report = _start(client, technician, setup, places)
    _complete(client, report["id"])
    _post(client, f"{API}/inspections/{report['id']}/submit/", {})
    client_for(client, supervisor)
    _post(client, f"{API}/inspections/{report['id']}/approve/", {})
    client_for(client, technician)
    url = f"{API}/inspections/{report['id']}/"
    assert client.patch(url, {"notes": "x"}, content_type="application/json").status_code == 400

    asset_id = setup["asset"].pk
    assert _post(client, f"{API}/assets/{asset_id}/new-report/", {"reason": ""}).status_code == 400
    created = _post(client, f"{API}/assets/{asset_id}/new-report/", {"reason": "Scratch missed"})
    second = client.get(f"{API}/inspections/{created.json()['id']}/").json()
    assert (second["version"], second["status"], second["conservation"]) == (2, "draft", "B")
    client.patch(
        f"{API}/inspections/{second['id']}/", {"conservation": "C"}, content_type="application/json"
    )
    client.post(f"{API}/inspections/{second['id']}/photos/", {"kind": "front", "file": _png()})
    assert _post(client, f"{API}/inspections/{second['id']}/submit/", {}).status_code == 200
    client_for(client, supervisor)
    _post(client, f"{API}/inspections/{second['id']}/approve/", {})
    first = InspectionReport.objects.get(pk=report["id"])
    assert (first.status, first.is_current) == (ReportStatus.SUPERSEDED, False)
    assert Asset.objects.get(pk=asset_id).condition_grade == "C1C"
    versions = client.get(f"{API}/assets/{asset_id}/reports/").json()
    assert [(v["version"], v["status"]) for v in versions] == [(2, "approved"), (1, "superseded")]


def test_return_to_draft(client, technician, supervisor, setup, places):
    report = _start(client, technician, setup, places)
    _complete(client, report["id"])
    _post(client, f"{API}/inspections/{report['id']}/submit/", {})
    client_for(client, supervisor)
    url = f"{API}/inspections/{report['id']}/return/"
    assert _post(client, url, {"notes": ""}).status_code == 400
    data = _post(client, url, {"notes": "Photo of the screen is blurred."}).json()
    assert (data["status"], data["review_notes"]) == ("draft", "Photo of the screen is blurred.")


def test_mark_sent(client, technician, supervisor, commercial, setup, places):
    report = _start(client, technician, setup, places)
    _complete(client, report["id"])
    _post(client, f"{API}/inspections/{report['id']}/submit/", {})
    client_for(client, supervisor)
    _post(client, f"{API}/inspections/{report['id']}/approve/", {})
    client_for(client, commercial)
    data = _post(client, f"{API}/inspections/{report['id']}/sent/", {}).json()
    assert data["sent_to_customer_at"]


# --- Catalogs --------------------------------------------------------------------------------


def test_penalty_periods_never_overlap_rn03(client, supervisor, notebook_class):
    client_for(client, supervisor)
    url = f"{API}/penalty-rates/"
    base = {"asset_class": notebook_class.id, "finding_kind": "damage", "value": "200"}
    assert (
        _post(
            client, url, {**base, "valid_from": "2026-01-01", "valid_to": "2026-06-30"}
        ).status_code
        == 201
    )
    overlap = _post(client, url, {**base, "valid_from": "2026-06-01"})
    assert "valid_from" in overlap.json()
    assert _post(client, url, {**base, "valid_from": "2026-07-01"}).status_code == 201
    # The rate on a date
    assert inspection.rate_for(notebook_class.id, "damage", date(2026, 3, 1)) == Decimal("200.00")
    assert inspection.rate_for(notebook_class.id, "damage", date(2025, 3, 1)) is None


def test_grade_levels(client, supervisor, technician):
    client_for(client, technician)
    levels = client.get(f"{API}/grade-levels/").json()
    assert [(level["domain"], level["code"]) for level in levels][:4] == [
        ("completeness", "C"),
        ("completeness", "P"),
        ("completeness", "I"),
        ("conservation", "A"),
    ]
    assert (
        client.patch(
            f"{API}/grade-levels/{levels[0]['id']}/",
            {"description": "x"},
            content_type="application/json",
        ).status_code
        == 403
    )
    client_for(client, supervisor)
    response = client.patch(
        f"{API}/grade-levels/{levels[0]['id']}/",
        {"description": "Everything", "code": "Z"},
        content_type="application/json",
    )
    assert (response.json()["description"], response.json()["code"]) == ("Everything", "C")


def test_lot_erasure_tools(client, supervisor, receiver, setup):
    lot = setup["lot"]
    client_for(client, receiver)
    rows = client.get(f"{API}/lots/{lot.id}/erasure-tools/").json()
    assert rows[0]["asset_class_name"] == "Notebook"
    assert rows[0]["definition"]["method"] == "purge"
    payload = {
        "definitions": [
            {"asset_class": rows[0]["asset_class"], "tool": setup["tool"].id, "method": "purge"}
        ]
    }
    assert (
        client.put(
            f"{API}/lots/{lot.id}/erasure-tools/", payload, content_type="application/json"
        ).status_code
        == 403
    )
    client_for(client, supervisor)
    bad = {
        "definitions": [
            {"asset_class": rows[0]["asset_class"], "tool": setup["tool"].id, "method": "destroy"}
        ]
    }
    assert (
        client.put(
            f"{API}/lots/{lot.id}/erasure-tools/", bad, content_type="application/json"
        ).status_code
        == 400
    )


# --- Part harvesting ---------------------------------------------------------------------------


def test_disassemble_a_scrap_asset(client, technician, setup, notebook_class, admin):
    asset = setup["asset"]
    from . import services

    services.change_status(asset, to_status=AssetStatus.IN_INSPECTION, user=admin)
    services.change_status(asset, to_status=AssetStatus.SCRAP, user=admin)
    acme = Manufacturer.objects.create(name="Acme")
    screen = AssetModel.objects.create(
        manufacturer=acme, name="Screen 14", asset_class=notebook_class
    )
    screws = AssetModel.objects.create(
        manufacturer=acme, name="Screws", asset_class=notebook_class, tracking=Tracking.QUANTITY
    )
    client_for(client, technician)
    response = _post(
        client,
        f"{API}/assets/{asset.id}/disassemble/",
        {
            "parts": [
                {"asset_model": screen.id, "quantity": 1},
                {"asset_model": screws.id, "quantity": 12},
            ]
        },
    )
    assert response.status_code == 201, response.json()
    (part,) = response.json()
    assert (part["status"], part["parent_asset"]) == ("awaiting_inspection", asset.id)
    asset.refresh_from_db()
    assert asset.status == AssetStatus.WRITTEN_OFF
    assert screws.balances.get().quantity == 12
