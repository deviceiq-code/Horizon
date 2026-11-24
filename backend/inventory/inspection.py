"""Inspection of assets: versioned reports, photos, findings valued by the penalty table,
data erasure certificates, approval and part harvesting (RN-03, RN-04, RN-09 to RN-13).

Status and places of assets change only through inventory.services (RN-07). Every operation
runs in one transaction; refusals raise states.DomainError (translated).
"""

import re
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from catalogs.models import PhotoKind, Tracking
from catalogs.serializers import spec_messages
from catalogs.specs import SpecError, snapshot_values
from pricing.documents import PHOTO_EXTENSIONS, check_document, clean_filename, content_type_for

from . import services
from .grades import recommended_destination, suggest_completeness, suggest_functioning
from .models import (
    GRADE_CODES,
    Asset,
    Cleaning,
    ErasureCertificate,
    ErasureResult,
    Finding,
    FindingKind,
    FindingStatus,
    GradeDomain,
    InspectionReport,
    Location,
    LotErasureTool,
    PenaltyRate,
    ReportPhoto,
    ReportStatus,
    SerialStatus,
)
from .receiving import attachment_messages
from .states import AreaType, AssetStatus, DomainError

CAN_START_FROM = (AssetStatus.AWAITING_INSPECTION, AssetStatus.BLOCKED)


# --- Penalty table ---------------------------------------------------------------------------


def rate_for(asset_class_id: int, kind: str, on: date) -> Decimal | None:
    """The penalty valid on a date for an asset class and a kind of finding (None: no rate)."""
    rate = (
        PenaltyRate.objects.filter(
            asset_class_id=asset_class_id, finding_kind=kind, valid_from__lte=on
        )
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=on))
        .order_by("-valid_from")
        .first()
    )
    return rate.value if rate else None


def _report_date(report: InspectionReport) -> date:
    return timezone.localdate(report.started_at)


def apply_values(report: InspectionReport) -> None:
    """Every finding not set by a supervisor takes the table's value on the report's date."""
    class_id = report.asset.asset_model.asset_class_id
    for finding in report.findings.exclude(status=FindingStatus.CANCELLED).filter(
        value_overridden=False
    ):
        value = rate_for(class_id, finding.kind, _report_date(report))
        if finding.value != value:
            finding.value = value
            finding.save(update_fields=["value"])


# --- Starting and the draft --------------------------------------------------------------------


@transaction.atomic
def start_inspection(asset: Asset, *, bench: Location, user) -> InspectionReport:
    """The asset is read at a bench: it goes there, IN_INSPECTION, and a draft report starts
    (or the one already being prepared is resumed)."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    open_report = asset.reports.filter(
        status__in=[ReportStatus.DRAFT, ReportStatus.AWAITING_APPROVAL]
    ).first()
    if asset.status == AssetStatus.IN_INSPECTION and open_report:
        return open_report
    if asset.status not in CAN_START_FROM:
        raise DomainError(
            _("Only assets awaiting inspection (or blocked) can be inspected."), field="asset"
        )
    if asset.held_for_dispute:
        raise DomainError(_("This asset is held for a dispute."), field="asset")
    if bench.area_type != AreaType.BENCH or not bench.is_active:
        raise DomainError(_("Read an active bench."), field="bench")
    services.change_status(asset, to_status=AssetStatus.IN_INSPECTION, user=user, to_location=bench)
    if open_report:
        return open_report
    last = asset.reports.aggregate(last=Max("version"))["last"] or 0
    current = asset.reports.filter(is_current=True).first()
    report = InspectionReport.objects.create(asset=asset, version=last + 1, technician=user)
    if current is not None:
        _copy_from(current, report)
    return report


def _copy_from(source: InspectionReport, report: InspectionReport) -> None:
    """A new version starts as the current one (its findings suggested again)."""
    for field in (
        "conservation",
        "functioning",
        "completeness",
        "failed_components",
        "irreparable",
        "missing_items",
        "checklist_done",
        "test_results",
        "cleaning",
        "notes",
    ):
        setattr(report, field, getattr(source, field))
    report.save()
    for finding in source.findings.exclude(status=FindingStatus.CANCELLED):
        Finding.objects.create(
            report=report,
            kind=finding.kind,
            block_type=finding.block_type,
            item=finding.item,
            description=finding.description,
            value=finding.value,
            value_overridden=finding.value_overridden,
            value_justification=finding.value_justification,
            automatic=finding.automatic,
        )


def lock_draft(report: InspectionReport) -> InspectionReport:
    report = InspectionReport.objects.select_for_update().get(pk=report.pk)
    if report.status != ReportStatus.DRAFT:
        raise DomainError(_("Only a draft report can be changed."), field="status")
    return report


@transaction.atomic
def sync_report(report: InspectionReport) -> InspectionReport:
    """After the draft changes: the automatic findings follow the missing kit items and the
    cleaning; every finding takes its table value."""
    report = lock_draft(report)
    wanted = {(FindingKind.MISSING_ITEM, item) for item in report.missing_items}
    if report.cleaning == Cleaning.HEAVY:
        wanted.add((FindingKind.HEAVY_CLEANING, ""))
    existing = {(f.kind, f.item): f for f in report.findings.filter(automatic=True)}
    for key, finding in existing.items():
        if key not in wanted:
            finding.delete()
    for kind, item in wanted - set(existing):
        Finding.objects.create(report=report, kind=kind, item=item, automatic=True)
    apply_values(report)
    return report


@transaction.atomic
def complete_serial(report: InspectionReport, serial: str) -> Asset:
    """The serial number read at inspection (pending since triage): model's pattern and unique
    per model (RN-05)."""
    lock_draft(report)
    asset = Asset.objects.select_for_update().get(pk=report.asset_id)
    serial = "".join((serial or "").split()).upper()
    if not serial:
        raise DomainError(_("Read the serial number."), field="serial")
    pattern = asset.asset_model.serial_regex
    if pattern and not re.fullmatch(pattern, serial):
        raise DomainError(
            _("This serial number does not match the model's pattern."), field="serial"
        )
    duplicate = Asset.objects.filter(
        asset_model=asset.asset_model, serial=serial, serial_status=SerialStatus.CAPTURED
    ).exclude(pk=asset.pk)
    if duplicate.exists():
        raise DomainError(
            _("An asset of this model with this serial number already exists."), field="serial"
        )
    asset.serial = serial
    asset.serial_status = SerialStatus.CAPTURED
    asset.no_serial_reason = ""
    asset.save(update_fields=["serial", "serial_status", "no_serial_reason", "updated_at"])
    return asset


@transaction.atomic
def set_specs(report: InspectionReport, values: dict) -> Asset:
    """The asset's own specification values (required ones are checked when submitting)."""
    lock_draft(report)
    asset = Asset.objects.select_for_update().get(pk=report.asset_id)
    template = asset.asset_model.asset_class.spec_template
    try:
        snapshot = snapshot_values(
            [{**f, "required": False} for f in template], values, spec_messages()
        )
    except SpecError as exc:
        raise DomainError(_("Check the specification values."), field="specs") from exc
    required = {f["key"]: f["required"] for f in template}
    asset.specs = [{**f, "required": required[f["key"]]} for f in snapshot]
    asset.save(update_fields=["specs", "updated_at"])
    return asset


@transaction.atomic
def add_photo(report: InspectionReport, *, kind: str, upload, user, description="") -> ReportPhoto:
    lock_draft(report)
    name = clean_filename(upload.name or "")
    errors = check_document(
        name,
        upload.size,
        settings.PRICE_DOCUMENT_MAX_MB * 1024 * 1024,
        attachment_messages(),
        PHOTO_EXTENSIONS,
    )
    if errors:
        raise DomainError(" ".join(str(e) for e in errors), field="file")
    photo = ReportPhoto(
        report=report,
        kind=kind,
        name=name,
        size=upload.size,
        content_type=content_type_for(name),
        description=" ".join((description or "").split())[:200],
        uploaded_by=user,
    )
    photo.file.save(name, upload, save=False)
    photo.save()
    return photo


# --- Data erasure ------------------------------------------------------------------------------


def lot_tool(asset: Asset) -> LotErasureTool | None:
    """The tool and method defined for the asset's lot and class (RN-04)."""
    if asset.lot_id is None:
        return None
    return (
        LotErasureTool.objects.filter(
            lot_id=asset.lot_id, asset_class_id=asset.asset_model.asset_class_id
        )
        .select_related("tool")
        .first()
    )


@transaction.atomic
def add_certificate(
    report: InspectionReport,
    *,
    user,
    result: str,
    disk_serial: str = "",
    upload=None,
    disk_model=None,
) -> ErasureCertificate:
    """A storage device erased with the lot's tool and method (RN-04). A failure removes the
    disk: it becomes a child asset in scrap, for physical destruction (RN-13)."""
    report = lock_draft(report)
    asset = report.asset
    if not asset.asset_model.has_storage:
        raise DomainError(_("This model has no data storage."), field="asset")
    definition = lot_tool(asset)
    if definition is None:
        raise DomainError(
            _("The erasure tool of this lot and asset class is not defined yet."), field="tool"
        )
    if result not in ErasureResult.values:
        raise DomainError(_("Choose the result."), field="result")
    if result == ErasureResult.SUCCESS and upload is None:
        raise DomainError(_("Attach the erasure certificate."), field="file")
    certificate = ErasureCertificate(
        asset=asset,
        report=report,
        disk_serial="".join((disk_serial or "").split()).upper(),
        tool=definition.tool,
        tool_version=definition.tool.version,
        method=definition.method,
        result=result,
        operator=user,
    )
    if result == ErasureResult.FAILURE:
        if disk_model is None:
            raise DomainError(_("Choose the model of the removed disk."), field="disk_model")
        certificate.removed_disk = services.register_child(
            asset,
            asset_model=disk_model,
            user=user,
            status=AssetStatus.SCRAP,
            serial=disk_serial,
            reason=_("Disk removed for destruction (erasure failed)."),
            document_ref=f"report:{report.pk}",
        )
    if upload is not None:
        name = clean_filename(upload.name or "")
        errors = check_document(
            name, upload.size, settings.PRICE_DOCUMENT_MAX_MB * 1024 * 1024, attachment_messages()
        )
        if errors:
            raise DomainError(" ".join(str(e) for e in errors), field="file")
        certificate.name = name
        certificate.file.save(name, upload, save=False)
    certificate.save()
    return certificate


def storage_cleared(asset: Asset) -> bool:
    """RN-12: an erasure succeeded, or a disk was removed for destruction."""
    return asset.erasures.filter(
        Q(result=ErasureResult.SUCCESS) | Q(removed_disk__isnull=False)
    ).exists()


# --- Submitting, approving, new versions ------------------------------------------------------


def suggestions(report: InspectionReport) -> dict:
    model = report.asset.asset_model
    return {
        "functioning": suggest_functioning(model.test_script, report.test_results),
        "completeness": suggest_completeness(model.kit_checklist, report.missing_items)
        if report.checklist_done
        else "",
        "destination": recommended_destination(
            list(
                report.findings.exclude(status=FindingStatus.CANCELLED).values_list(
                    "kind", flat=True
                )
            ),
            report.functioning,
            report.irreparable,
        ),
    }


def problems(report: InspectionReport) -> list[str]:
    """What still prevents submitting (empty: ready)."""
    asset, model = report.asset, report.asset.asset_model
    found = []
    if asset.serial_status == SerialStatus.PENDING:
        found.append(_("Read the serial number (pending since triage)."))
    missing_specs = [f["label"] for f in asset.specs if f.get("required") and not f.get("value")]
    if missing_specs:
        found.append(
            _("Fill in the specifications: %(fields)s.") % {"fields": ", ".join(missing_specs)}
        )
    kinds = set(report.photos.values_list("kind", flat=True))
    missing_photos = [k for k in model.asset_class.required_photo_kinds if k not in kinds]
    if missing_photos:
        found.append(
            _("Add the photos: %(kinds)s.")
            % {"kinds": ", ".join(str(PhotoKind(k).label) for k in missing_photos)}
        )
    if model.kit_checklist and not report.checklist_done:
        found.append(_("Check the kit."))
    unanswered = [item for item in model.test_script if item not in report.test_results]
    if unanswered:
        found.append(_("Answer the test script: %(items)s.") % {"items": ", ".join(unanswered)})
    for domain, field in (
        (GradeDomain.CONSERVATION, "conservation"),
        (GradeDomain.FUNCTIONING, "functioning"),
        (GradeDomain.COMPLETENESS, "completeness"),
    ):
        if getattr(report, field) not in GRADE_CODES[domain]:
            found.append(_("Grade the %(domain)s.") % {"domain": GradeDomain(domain).label.lower()})
    blocks = report.findings.filter(kind=FindingKind.ACCESS_BLOCK).exclude(
        status=FindingStatus.CANCELLED
    )
    if blocks.filter(block_type="").exists():
        found.append(_("Say the type of each access block."))
    destination = suggestions(report)["destination"]
    if model.has_storage and destination == "available" and not storage_cleared(asset):
        found.append(
            _("Erase the data (certificate) or remove the disk before the asset is available.")
        )
    return found


@transaction.atomic
def submit(report: InspectionReport, *, user) -> InspectionReport:
    report = sync_report(report)
    found = problems(report)
    if found:
        raise DomainError(" ".join(found), field="report")
    report.recommended_destination = suggestions(report)["destination"]
    report.status = ReportStatus.AWAITING_APPROVAL
    report.finished_at = timezone.now()
    report.review_notes = ""
    report.save()
    return report


@transaction.atomic
def return_to_draft(report: InspectionReport, *, user, notes: str) -> InspectionReport:
    report = InspectionReport.objects.select_for_update().get(pk=report.pk)
    if report.status != ReportStatus.AWAITING_APPROVAL:
        raise DomainError(_("Only a report awaiting approval can be sent back."), field="status")
    if not notes.strip():
        raise DomainError(_("Say what the technician must review."), field="notes")
    report.status = ReportStatus.DRAFT
    report.review_notes = notes.strip()
    report.save(update_fields=["status", "review_notes"])
    return report


@transaction.atomic
def approve(report: InspectionReport, *, user) -> InspectionReport:
    """Approve a report: it becomes the asset's current one (the previous is superseded), its
    findings are approved and the asset takes its grade and destination status."""
    report = InspectionReport.objects.select_for_update().get(pk=report.pk)
    if report.status != ReportStatus.AWAITING_APPROVAL:
        raise DomainError(_("Only a report awaiting approval can be approved."), field="status")
    if report.technician_id == user.pk:  # RN-10
        raise DomainError(_("Whoever prepared the report cannot approve it."), field="approved_by")
    apply_values(report)
    findings = report.findings.exclude(status=FindingStatus.CANCELLED)
    without_value = [f for f in findings if f.value is None]
    if without_value:  # RN-11
        raise DomainError(
            _("No penalty rate for: %(kinds)s. Add it to the penalty table first.")
            % {"kinds": ", ".join(sorted({str(f.get_kind_display()) for f in without_value}))},
            field="findings",
        )
    asset = report.asset
    destination = report.recommended_destination
    if asset.asset_model.has_storage and destination == "available" and not storage_cleared(asset):
        raise DomainError(
            _("Erase the data (certificate) or remove the disk before the asset is available."),
            field="report",
        )  # RN-12

    previous = asset.reports.select_for_update().filter(is_current=True).exclude(pk=report.pk)
    previous.update(is_current=False, status=ReportStatus.SUPERSEDED)
    findings.update(status=FindingStatus.APPROVED, approved_by=user)
    report.status = ReportStatus.APPROVED
    report.is_current = True
    report.approved_by = user
    report.approved_at = timezone.now()
    report.save()

    Asset.objects.filter(pk=asset.pk).update(condition_grade=report.grade)
    asset.refresh_from_db()
    target = {
        "available": AssetStatus.AVAILABLE,
        "blocked": AssetStatus.BLOCKED,
        "scrap": AssetStatus.SCRAP,
    }[destination]
    if asset.status != target:
        services.change_status(
            asset, to_status=target, user=user, document_ref=f"report:{report.pk}"
        )
    return report


@transaction.atomic
def new_version(asset: Asset, *, user, reason: str) -> InspectionReport:
    """A correction of an approved report: a new draft, starting as the current one (RN-09).
    The asset keeps its status and place until the new version is approved."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    if not reason.strip():
        raise DomainError(_("Say why a new version is needed."), field="reason")
    if asset.held_for_dispute:
        raise DomainError(
            _("This asset is held for a dispute: its report changes only through the dispute."),
            field="asset",
        )
    current = asset.reports.filter(is_current=True).first()
    if current is None:
        raise DomainError(_("This asset has no approved report yet."), field="asset")
    if asset.reports.filter(
        status__in=[ReportStatus.DRAFT, ReportStatus.AWAITING_APPROVAL]
    ).exists():
        raise DomainError(_("A report of this asset is already being prepared."), field="asset")
    report = InspectionReport.objects.create(
        asset=asset,
        version=(asset.reports.aggregate(last=Max("version"))["last"] or 0) + 1,
        technician=user,
        new_version_reason=reason.strip(),
    )
    _copy_from(current, report)
    return report


@transaction.atomic
def mark_sent(report: InspectionReport, *, user) -> InspectionReport:
    """The approved report was sent to the customer (the dispute period starts — Phase 4)."""
    report = InspectionReport.objects.select_for_update().get(pk=report.pk)
    if report.status != ReportStatus.APPROVED or not report.is_current:
        raise DomainError(_("Only the current approved report is sent."), field="status")
    if report.sent_to_customer_at is None:
        report.sent_to_customer_at = timezone.now()
        report.save(update_fields=["sent_to_customer_at"])
    return report


@transaction.atomic
def set_finding_value(finding: Finding, *, value: Decimal | None, justification: str) -> Finding:
    """A supervisor sets a finding's value (None: back to the table's), with a justification."""
    finding = Finding.objects.select_for_update().select_related("report").get(pk=finding.pk)
    if finding.report.status in (ReportStatus.APPROVED, ReportStatus.SUPERSEDED):
        raise DomainError(_("An approved report never changes."), field="value")
    if value is None:
        finding.value_overridden = False
        finding.value_justification = ""
        finding.save()
        apply_values(finding.report)
        finding.refresh_from_db()
        return finding
    if value < 0:
        raise DomainError(_("Enter a value of zero or more."), field="value")
    if not justification.strip():
        raise DomainError(_("Justify the new value."), field="value_justification")
    finding.value = value
    finding.value_overridden = True
    finding.value_justification = justification.strip()
    finding.save()
    return finding


# --- Part harvesting -------------------------------------------------------------------------


@transaction.atomic
def disassemble(asset: Asset, *, user, parts: list[dict], reason: str = "") -> list[Asset]:
    """A scrap asset is taken apart: unit parts become child assets (awaiting inspection),
    quantity parts enter the accessory balance where it is; the asset is written off."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    if asset.status != AssetStatus.SCRAP:
        raise DomainError(_("Only scrap assets are taken apart."), field="asset")
    if not parts:
        raise DomainError(_("List the parts taken."), field="parts")
    ref = f"disassembly:{asset.pk}"
    children = []
    for part in parts:
        model, quantity = part["asset_model"], int(part.get("quantity") or 1)
        if model.tracking == Tracking.UNIT:
            for _index in range(quantity):
                children.append(
                    services.register_child(
                        asset,
                        asset_model=model,
                        user=user,
                        status=AssetStatus.AWAITING_INSPECTION,
                        serial=part.get("serial", "") if quantity == 1 else "",
                        reason=reason,
                        document_ref=ref,
                    )
                )
        else:
            services.add_accessories(
                model,
                quantity,
                user=user,
                location=asset.current_location,
                document_ref=ref,
                reason=reason,
            )
    services.change_status(
        asset, to_status=AssetStatus.WRITTEN_OFF, user=user, document_ref=ref, reason=reason
    )
    return children
