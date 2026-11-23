"""Receiving: appointments' codes, lots, triage of units and accessories, attachments,
reconciliation against the expected list, occurrences and closing (RN-17, RN-18).

Status and places of assets change only through inventory.services (RN-07); this module calls
it. Every operation runs in one transaction; refusals raise states.DomainError.
"""

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from catalogs.models import AssetModel, Tracking
from pricing.documents import PHOTO_EXTENSIONS, check_document, clean_filename, content_type_for

from . import services
from .models import (
    AccessoryCondition,
    Appointment,
    AppointmentKind,
    AppointmentStatus,
    Asset,
    AttachmentKind,
    Container,
    ExpectedItem,
    Location,
    LotAttachment,
    LotStatus,
    Occurrence,
    OccurrenceStatus,
    ReceivingLot,
)
from .reconciliation import Expected, ReceivedUnit, reconcile
from .states import AreaType, AssetStatus, DomainError

PHOTO_KINDS = {
    AttachmentKind.PACKAGE_PHOTO,
    AttachmentKind.DAMAGE_PHOTO,
    AttachmentKind.NO_SERIAL_PHOTO,
}


# --- Codes per year --------------------------------------------------------------------------


def create_with_code(model, **fields):
    """Create a row with the next sequence of the current year (retried when another one took
    it at the same moment)."""
    year = timezone.localdate().year
    for _attempt in range(5):
        try:
            with transaction.atomic():
                last = (
                    model.objects.filter(year=year)
                    .order_by("-sequence")
                    .values_list("sequence", flat=True)
                    .first()
                )
                return model.objects.create(year=year, sequence=(last or 0) + 1, **fields)
        except IntegrityError:
            continue
    raise DomainError(_("Please try again."))


# --- Appointments ------------------------------------------------------------------------------


def overlapping(appointment: Appointment):
    """Other appointments of the warehouse at the same time (not cancelled): only warned about."""
    return (
        Appointment.objects.filter(
            warehouse_id=appointment.warehouse_id,
            starts_at__lt=appointment.ends_at,
            ends_at__gt=appointment.starts_at,
        )
        .exclude(pk=appointment.pk)
        .exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])
    )


APPOINTMENT_MOVES = {
    AppointmentStatus.SCHEDULED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.IN_PROGRESS,
    },
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.SCHEDULED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.IN_PROGRESS,
    },
    AppointmentStatus.IN_PROGRESS: {AppointmentStatus.DONE},
    AppointmentStatus.CANCELLED: {AppointmentStatus.SCHEDULED},
    AppointmentStatus.NO_SHOW: {AppointmentStatus.SCHEDULED},
    AppointmentStatus.DONE: set(),
}


@transaction.atomic
def set_appointment_status(appointment: Appointment, status: str) -> Appointment:
    appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
    if status not in APPOINTMENT_MOVES[appointment.status]:
        raise DomainError(
            _("An appointment cannot go from %(before)s to %(after)s.")
            % {
                "before": AppointmentStatus(appointment.status).label,
                "after": AppointmentStatus(status).label,
            },
            field="status",
        )
    # A receiving starts by opening its lot; it is done when the lot closes
    if appointment.kind == AppointmentKind.RECEIVING and status in (
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.DONE,
    ):
        raise DomainError(
            _("A receiving starts when its lot is opened and ends when the lot is closed."),
            field="status",
        )
    appointment.status = status
    appointment.save(update_fields=["status", "updated_at"])
    return appointment


# --- Lots --------------------------------------------------------------------------------------


@transaction.atomic
def open_lot(
    *,
    warehouse,
    dock: Location,
    user,
    customer=None,
    appointment: Appointment | None = None,
    fiscal_document_number: str = "",
    notes: str = "",
) -> ReceivingLot:
    """A vehicle arrived: open its lot (from its receiving appointment, or unscheduled)."""
    if appointment is not None:
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
        if appointment.kind != AppointmentKind.RECEIVING:
            raise DomainError(_("Choose a receiving appointment."), field="appointment")
        if appointment.status not in (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED):
            raise DomainError(
                _("This appointment is not waiting for the vehicle."), field="appointment"
            )
        if ReceivingLot.objects.filter(appointment=appointment).exists():
            raise DomainError(_("This appointment already has a lot."), field="appointment")
        warehouse = appointment.warehouse
        customer = appointment.customer
    if customer is None:
        raise DomainError(_("Choose the customer."), field="customer")
    if dock.warehouse_id != warehouse.id or dock.area_type != AreaType.DOCK or not dock.is_active:
        raise DomainError(_("Read an active dock of this warehouse."), field="dock")

    lot = create_with_code(
        ReceivingLot,
        warehouse=warehouse,
        customer=customer,
        appointment=appointment,
        dock=dock,
        fiscal_document_number=" ".join(fiscal_document_number.split()),
        notes=notes,
        opened_by=user,
    )
    if appointment is not None:
        appointment.status = AppointmentStatus.IN_PROGRESS
        appointment.save(update_fields=["status", "updated_at"])
    return lot


def _lock_open(lot: ReceivingLot) -> ReceivingLot:
    lot = ReceivingLot.objects.select_for_update().get(pk=lot.pk)
    if lot.status == LotStatus.CLOSED:
        raise DomainError(_("This lot is closed."), field="lot")
    return lot


def _check_container_at(container: Container | None, warehouse) -> None:
    if container is not None and container.current_location.warehouse_id != warehouse.id:
        raise DomainError(_("This container is in another warehouse."), field="container")


@transaction.atomic
def triage_unit(
    lot: ReceivingLot,
    *,
    user,
    asset_model: AssetModel,
    horizon_id: str = "",
    serial: str = "",
    no_serial_reason: str = "",
    container: Container | None = None,
    photo=None,
) -> Asset:
    """One unit read at triage: its label (pre-printed, or a new ID), model and serial number.
    Without a serial, the reason and a photo are required."""
    lot = _lock_open(lot)
    if not "".join((serial or "").split()) and photo is None:
        raise DomainError(_("Without a serial number, take a photo of the asset."), field="photo")
    _check_container_at(container, lot.warehouse)
    if container is not None and container.current_location.area_type != AreaType.DOCK:
        raise DomainError(_("At triage, use a container that is at a dock."), field="container")
    asset = services.register_entry(
        asset_model=asset_model,
        location=lot.dock,
        container=container,
        user=user,
        serial=serial,
        no_serial_reason=no_serial_reason,
        horizon_id=horizon_id,
        document_ref=f"lot:{lot.pk}",
        lot=lot,
        customer=lot.customer,
    )
    if photo is not None:
        add_attachment(
            lot, kind=AttachmentKind.NO_SERIAL_PHOTO, upload=photo, user=user, asset=asset
        )
    return asset


def _scrap_place(container: Container | None, location: Location | None):
    place = container.current_location if container is not None else location
    if place is None or place.area_type != AreaType.SCRAP:
        raise DomainError(_("Damaged accessories go to a scrap area."), field="scrap_destination")


@transaction.atomic
def triage_accessories(
    lot: ReceivingLot,
    *,
    user,
    asset_model: AssetModel,
    quantity: int = 0,
    container: Container | None = None,
    damaged_quantity: int = 0,
    scrap_container: Container | None = None,
    scrap_location: Location | None = None,
) -> None:
    """Accessories tracked by quantity: the good ones into a container (or the dock), the
    damaged ones to a scrap area."""
    lot = _lock_open(lot)
    if asset_model.tracking != Tracking.QUANTITY:
        raise DomainError(
            _("This model is controlled by unit: read each one."), field="asset_model"
        )
    if quantity < 0 or damaged_quantity < 0 or quantity + damaged_quantity < 1:
        raise DomainError(_("Enter a quantity of at least 1."), field="quantity")
    ref = f"lot:{lot.pk}"
    if quantity:
        _check_container_at(container, lot.warehouse)
        services.add_accessories(
            asset_model,
            quantity,
            user=user,
            container=container,
            location=None if container else lot.dock,
            document_ref=ref,
        )
    if damaged_quantity:
        _scrap_place(scrap_container, scrap_location)
        _check_container_at(scrap_container, lot.warehouse)
        if scrap_location is not None and scrap_location.warehouse_id != lot.warehouse_id:
            raise DomainError(
                _("This location is in another warehouse."), field="scrap_destination"
            )
        services.add_accessories(
            asset_model,
            damaged_quantity,
            user=user,
            container=scrap_container,
            location=None if scrap_container else scrap_location,
            condition=AccessoryCondition.SCRAP,
            document_ref=ref,
        )


def received_accessories(lot: ReceivingLot) -> dict[int, int]:
    """Accessory units entered by the lot's triage, per model (good and scrap)."""
    totals: dict[int, int] = {}
    for model_id, quantity in lot_accessory_events(lot).values_list(
        "accessory_model_id", "quantity"
    ):
        totals[model_id] = totals.get(model_id, 0) + quantity
    return totals


def lot_accessory_events(lot: ReceivingLot):
    from .models import EventKind, MovementEvent

    return MovementEvent.objects.filter(
        document_ref=f"lot:{lot.pk}", kind=EventKind.ENTRY, accessory_model__isnull=False
    )


# --- Attachments ---------------------------------------------------------------------------


def attachment_messages() -> dict[str, str]:
    return {
        "bad_type": _("This type of file is not accepted. Accepted: %(types)s."),
        "too_large": _("The file is too large (maximum %(max)s MB)."),
        "empty": _("The file is empty."),
    }


def add_attachment(lot, *, kind: str, upload, user, asset=None, occurrence=None) -> LotAttachment:
    name = clean_filename(upload.name or "")
    allowed = PHOTO_EXTENSIONS if kind in PHOTO_KINDS else None
    errors = check_document(
        name,
        upload.size,
        settings.PRICE_DOCUMENT_MAX_MB * 1024 * 1024,
        attachment_messages(),
        **({"allowed": allowed} if allowed else {}),
    )
    if errors:
        raise DomainError(" ".join(str(e) for e in errors), field="file")
    attachment = LotAttachment(
        lot=lot,
        kind=kind,
        asset=asset,
        occurrence=occurrence,
        name=name,
        size=upload.size,
        content_type=content_type_for(name),
        uploaded_by=user,
    )
    attachment.file.save(name, upload, save=False)
    attachment.save()
    return attachment


# --- Reconciliation, occurrences and closing ------------------------------------------------


def _finding_key(kind, model_id, quantity, expected_serial, received_serial, asset_id):
    return (kind, model_id, quantity, expected_serial, received_serial, asset_id)


@transaction.atomic
def reconcile_lot(lot: ReceivingLot, *, user) -> list[Occurrence]:
    """Compare what arrived with the expected list and record the differences as automatic
    occurrences. Running again keeps those still found (same records), removes the open ones
    no longer found and never recreates a resolved or accepted one."""
    lot = _lock_open(lot)
    lot.status = LotStatus.RECONCILING
    lot.save(update_fields=["status"])
    if lot.appointment_id is None:
        return []

    expected_rows = list(ExpectedItem.objects.filter(appointment_id=lot.appointment_id))
    model_ids = {row.asset_model_id for row in expected_rows}
    received_counts = received_accessories(lot)
    model_ids |= set(received_counts)
    accessory_models = set(
        AssetModel.objects.filter(pk__in=model_ids, tracking=Tracking.QUANTITY).values_list(
            "pk", flat=True
        )
    )
    findings = reconcile(
        [Expected(r.asset_model_id, r.serial, r.quantity) for r in expected_rows],
        [
            ReceivedUnit(a.pk, a.asset_model_id, a.serial if a.serial_status == "captured" else "")
            for a in lot.assets.all()
        ],
        received_counts,
        accessory_models,
    )
    existing = {
        _finding_key(
            o.kind, o.asset_model_id, o.quantity, o.expected_serial, o.received_serial, o.asset_id
        ): o
        for o in lot.occurrences.filter(automatic=True)
    }
    found = {
        _finding_key(
            f.kind, f.model_id, f.quantity, f.expected_serial, f.received_serial, f.asset_id
        )
        for f in findings
    }
    for key, occurrence in existing.items():
        if key not in found and occurrence.status == OccurrenceStatus.OPEN:
            occurrence.delete()
    kept = set(existing)
    created = []
    for f in findings:
        key = _finding_key(
            f.kind, f.model_id, f.quantity, f.expected_serial, f.received_serial, f.asset_id
        )
        if key in kept:
            continue
        created.append(
            Occurrence.objects.create(
                kind=f.kind,
                lot=lot,
                asset_id=f.asset_id,
                asset_model_id=f.model_id,
                quantity=f.quantity,
                expected_serial=f.expected_serial,
                received_serial=f.received_serial,
                automatic=True,
                created_by=user,
            )
        )
    return created


@transaction.atomic
def resolve_occurrence(occurrence: Occurrence, *, user, resolution: str) -> Occurrence:
    occurrence = Occurrence.objects.select_for_update().get(pk=occurrence.pk)
    if occurrence.status != OccurrenceStatus.OPEN:
        raise DomainError(_("This occurrence is no longer open."), field="status")
    if not resolution.strip():
        raise DomainError(_("Describe how it was resolved."), field="resolution")
    occurrence.status = OccurrenceStatus.RESOLVED
    occurrence.resolution = resolution.strip()
    occurrence.resolved_by = user
    occurrence.resolved_at = timezone.now()
    occurrence.save()
    return occurrence


@transaction.atomic
def accept_occurrence(occurrence: Occurrence, *, user, resolution: str) -> Occurrence:
    """The divergence stands as it is (supervisors only — checked by the API)."""
    occurrence = Occurrence.objects.select_for_update().get(pk=occurrence.pk)
    if occurrence.status != OccurrenceStatus.OPEN:
        raise DomainError(_("This occurrence is no longer open."), field="status")
    if not resolution.strip():
        raise DomainError(_("Say why it is accepted."), field="resolution")
    occurrence.status = OccurrenceStatus.ACCEPTED
    occurrence.resolution = resolution.strip()
    occurrence.resolved_by = user
    occurrence.resolved_at = timezone.now()
    occurrence.save()
    return occurrence


def close_lot(lot: ReceivingLot, *, user) -> ReceivingLot:
    """Reconcile once more and close: only with every occurrence resolved or accepted (RN-18).
    The lot's assets go to AWAITING_INSPECTION (put away in the inspection queue by reading
    them, or their containers, in Movement). The reconciliation is kept even when closing is
    refused (its own transaction)."""
    reconcile_lot(lot, user=user)
    return _close(lot, user=user)


@transaction.atomic
def _close(lot: ReceivingLot, *, user) -> ReceivingLot:
    lot = _lock_open(lot)
    pending = lot.occurrences.filter(status=OccurrenceStatus.OPEN).count()
    if pending:
        raise DomainError(
            _("Resolve or accept the %(count)d open occurrences first.") % {"count": pending},
            field="occurrences",
        )
    for asset in lot.assets.filter(status=AssetStatus.IN_TRIAGE):
        services.change_status(
            asset,
            to_status=AssetStatus.AWAITING_INSPECTION,
            user=user,
            document_ref=f"lot:{lot.pk}",
        )
    lot.status = LotStatus.CLOSED
    lot.closed_by = user
    lot.closed_at = timezone.now()
    lot.save(update_fields=["status", "closed_by", "closed_at"])
    if lot.appointment_id:
        Appointment.objects.filter(pk=lot.appointment_id).update(
            status=AppointmentStatus.DONE, updated_at=timezone.now()
        )
    return lot
