"""Transfers between warehouses (Phase 6). The only code that changes a transfer; asset
statuses and places still change only through inventory.services (RN-07).

request (items: assets — available, scrap, blocked or awaiting inspection, never held for a
dispute —, containers = their assets, accessories by quantity) → approve (supervisor) → pick:
read each ID or container against the list (RN-24: a divergence blocks the sending) → send
(fiscal document): assets IN_TRANSIT at the virtual location, keeping their status →
receive at the destination in one step: read the location, then each ID or container: back
to the status they had, there (RN-02) → finish: what did not arrive becomes a shortage;
surpluses and damage (registered while receiving) are occurrences too. In transit longer than
`transit_days` → alert (RN-25, daily routine).
"""

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from catalogs.models import Tracking
from pricing.documents import check_document, clean_filename, content_type_for

from . import services
from .models import (
    BEFORE_SENDING,
    OPEN_DISPOSAL,
    OPEN_TRANSFER,
    TRANSFERABLE,
    AccessoryBalance,
    AccessoryCondition,
    Asset,
    Container,
    DisposalItem,
    EventKind,
    Location,
    MovementEvent,
    Occurrence,
    OccurrenceKind,
    OccurrenceStatus,
    Transfer,
    TransferFile,
    TransferFileKind,
    TransferItem,
    TransferStatus,
)
from .receiving import attachment_messages, create_with_code
from .states import AssetStatus, DomainError

MAX_TRANSIT_DAYS = 90


# --- Header ------------------------------------------------------------------------------------


def _check_days(days: int) -> None:
    if not 1 <= days <= MAX_TRANSIT_DAYS:
        raise DomainError(
            _("Enter from 1 to %(max)d days.") % {"max": MAX_TRANSIT_DAYS}, field="transit_days"
        )


def create(
    *,
    origin,
    destination,
    reason: str,
    user,
    transit_days: int = 5,
    notes: str = "",
    keywords=None,
) -> Transfer:
    if origin is None or destination is None:
        raise DomainError(_("Choose both warehouses."), field="destination")
    if origin.pk == destination.pk:
        raise DomainError(_("Choose another warehouse as the destination."), field="destination")
    if not (origin.is_active and destination.is_active):
        raise DomainError(_("Both warehouses must be active."), field="destination")
    if not reason.strip():
        raise DomainError(_("Say why the assets are transferred."), field="reason")
    _check_days(transit_days)
    return create_with_code(
        Transfer,
        origin=origin,
        destination=destination,
        reason=reason.strip(),
        transit_days=transit_days,
        notes=notes,
        keywords=keywords or [],
        requested_by=user,
    )


def _lock(transfer: Transfer, *statuses) -> Transfer:
    transfer = Transfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.status not in statuses:
        raise DomainError(
            _("Not possible while the transfer is %(status)s.")
            % {"status": TransferStatus(transfer.status).label},
            field="transfer",
        )
    return transfer


@transaction.atomic
def update_header(transfer: Transfer, **fields) -> Transfer:
    """Reason, transit days, notes and keywords before sending; the fiscal document's number
    until it is sent."""
    transfer = _lock(transfer, *BEFORE_SENDING)
    if "reason" in fields and not str(fields["reason"]).strip():
        raise DomainError(_("Say why the assets are transferred."), field="reason")
    if "transit_days" in fields:
        _check_days(fields["transit_days"])
    for name, value in fields.items():
        setattr(transfer, name, value.strip() if isinstance(value, str) else value)
    transfer.save()
    return transfer


# --- Items -------------------------------------------------------------------------------------


def open_transfer_of(asset: Asset) -> Transfer | None:
    item = (
        TransferItem.objects.filter(asset=asset, transfer__status__in=OPEN_TRANSFER)
        .select_related("transfer")
        .first()
    )
    return item.transfer if item else None


def check_not_in_transfer(asset: Asset) -> None:
    """For other operations (reserving for a disposal, starting an inspection…)."""
    transfer = open_transfer_of(asset)
    if transfer is not None:
        raise DomainError(
            _("This asset is in transfer %(code)s.") % {"code": transfer.code}, field="asset"
        )


def _check_eligible(transfer: Transfer, asset: Asset, *, adding: bool) -> None:
    if asset.held_for_dispute:
        raise DomainError(
            _("%(asset)s is held for a dispute and cannot be transferred.")
            % {"asset": asset.horizon_id},
            field="code",
        )
    if asset.status not in TRANSFERABLE:
        raise DomainError(
            _("%(asset)s is %(status)s: it cannot be transferred.")
            % {"asset": asset.horizon_id, "status": AssetStatus(asset.status).label},
            field="code",
        )
    if asset.current_location.warehouse_id != transfer.origin_id:
        raise DomainError(
            _("%(asset)s is not at warehouse %(code)s.")
            % {"asset": asset.horizon_id, "code": transfer.origin.code},
            field="code",
        )
    if adding:
        other = open_transfer_of(asset)
        if other is not None:
            raise DomainError(
                _("%(asset)s is already in transfer %(code)s.")
                % {"asset": asset.horizon_id, "code": other.code},
                field="code",
            )
        from .disposals import open_disposal_of

        disposal = open_disposal_of(asset)
        if disposal is not None:
            raise DomainError(
                _("%(asset)s is in disposal %(code)s.")
                % {"asset": asset.horizon_id, "code": disposal.code},
                field="code",
            )


@transaction.atomic
def add_asset(transfer: Transfer, asset: Asset) -> TransferItem:
    transfer = _lock(transfer, TransferStatus.REQUESTED)
    asset = Asset.objects.select_for_update().select_related("current_location").get(pk=asset.pk)
    _check_eligible(transfer, asset, adding=True)
    return TransferItem.objects.create(transfer=transfer, asset=asset)


@transaction.atomic
def add_container(transfer: Transfer, container: Container) -> list[TransferItem]:
    """Every asset in the container (all must be eligible, or none is added)."""
    transfer = _lock(transfer, TransferStatus.REQUESTED)
    assets = list(
        Asset.objects.select_for_update()
        .select_related("current_location")
        .filter(current_container=container)
    )
    if not assets:
        raise DomainError(_("This container is empty."), field="code")
    added = []
    for asset in assets:
        if transfer.items.filter(asset=asset).exists():
            continue
        _check_eligible(transfer, asset, adding=True)
        added.append(TransferItem.objects.create(transfer=transfer, asset=asset))
    return added


def _committed(asset_model, warehouse, condition) -> int:
    """Units of an accessory model that open disposals and transfers of a warehouse will still
    take from its balances (not picked yet)."""
    total = 0
    for model, filters in (
        (DisposalItem, {"disposal__warehouse": warehouse, "disposal__status__in": OPEN_DISPOSAL}),
        (TransferItem, {"transfer__origin": warehouse, "transfer__status__in": BEFORE_SENDING}),
    ):
        for quantity, picked in model.objects.filter(
            accessory_model=asset_model, condition=condition, **filters
        ).values_list("quantity", "picked_quantity"):
            total += quantity - picked
    return total


def _stock(asset_model, warehouse, condition) -> int:
    return (
        AccessoryBalance.objects.filter(asset_model=asset_model, condition=condition)
        .filter(
            Q(location__warehouse=warehouse) | Q(container__current_location__warehouse=warehouse)
        )
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )


@transaction.atomic
def add_accessory(
    transfer: Transfer, asset_model, quantity: int, *, condition: str = AccessoryCondition.GOOD
) -> TransferItem:
    transfer = _lock(transfer, TransferStatus.REQUESTED)
    if asset_model.tracking != Tracking.QUANTITY:
        raise DomainError(
            _("Only models controlled by quantity are added by quantity."), field="asset_model"
        )
    if quantity < 1:
        raise DomainError(_("Enter a quantity of at least 1."), field="quantity")
    if condition not in AccessoryCondition.values:
        raise DomainError(_("Choose the condition."), field="condition")
    free = _stock(asset_model, transfer.origin, condition) - _committed(
        asset_model, transfer.origin, condition
    )
    if quantity > free:
        raise DomainError(
            _("Only %(available)d available in this warehouse.") % {"available": max(free, 0)},
            field="quantity",
        )
    return TransferItem.objects.create(
        transfer=transfer, accessory_model=asset_model, quantity=quantity, condition=condition
    )


@transaction.atomic
def remove_item(item: TransferItem) -> None:
    _lock(item.transfer, TransferStatus.REQUESTED)
    item.delete()


@transaction.atomic
def approve(transfer: Transfer, *, user) -> Transfer:
    transfer = _lock(transfer, TransferStatus.REQUESTED)
    if not transfer.items.exists():
        raise DomainError(_("Add the assets or accessories to transfer."), field="transfer")
    transfer.status = TransferStatus.APPROVED
    transfer.approved_by = user
    transfer.approved_at = timezone.now()
    transfer.save()
    return transfer


# --- Picking at the origin (RN-24) ---------------------------------------------------------------


def _mark_picked(item: TransferItem, user, *, container=None, quantity=1) -> None:
    item.picked_quantity += quantity
    item.picked_at = timezone.now()
    item.picked_by = user
    item.container = container
    item.save(update_fields=["picked_quantity", "picked_at", "picked_by", "container"])


def _start_picking(transfer: Transfer) -> None:
    if transfer.status == TransferStatus.APPROVED:
        transfer.status = TransferStatus.PICKING
        transfer.save(update_fields=["status", "updated_at"])


@transaction.atomic
def pick(transfer: Transfer, target, *, user) -> list[TransferItem]:
    """An asset or a container read at the origin: it must be on the list (RN-24). A container
    stands for all its assets, which must all be on the list; they travel in it."""
    transfer = _lock(transfer, TransferStatus.APPROVED, TransferStatus.PICKING)
    if isinstance(target, Container):
        assets = list(Asset.objects.filter(current_container=target))
        if not assets:
            raise DomainError(_("This container is empty."), field="code")
        container = target
    else:
        assets, container = [target], None
    items = []
    for asset in assets:
        item = (
            TransferItem.objects.select_for_update(of=("self",))
            .filter(transfer=transfer, asset=asset)
            .select_related("asset__current_location")
            .first()
        )
        if item is None:
            raise DomainError(
                _("%(asset)s is not in this transfer.") % {"asset": asset.horizon_id},
                field="code",
            )
        if item.picked_quantity and container is None:
            raise DomainError(
                _("%(asset)s was already picked.") % {"asset": asset.horizon_id}, field="code"
            )
        _check_eligible(transfer, item.asset, adding=False)
        items.append(item)
    for item in items:
        item.picked_quantity = 0
        _mark_picked(item, user, container=container)
    _start_picking(transfer)
    return items


@transaction.atomic
def pick_accessory(
    transfer: Transfer,
    item: TransferItem,
    quantity: int,
    *,
    user,
    container: Container | None = None,
    location: Location | None = None,
) -> TransferItem:
    transfer = _lock(transfer, TransferStatus.APPROVED, TransferStatus.PICKING)
    item = TransferItem.objects.select_for_update().get(pk=item.pk, transfer=transfer)
    if item.accessory_model_id is None:
        raise DomainError(_("Read the asset's ID."), field="item")
    if quantity < 1 or item.picked_quantity + quantity > item.quantity:
        raise DomainError(
            _("Only %(left)d left to pick.") % {"left": item.quantity - item.picked_quantity},
            field="quantity",
        )
    place = container.current_location if container is not None else location
    if place is None or place.warehouse_id != transfer.origin_id:
        raise DomainError(
            _("Read a container or location of warehouse %(code)s.")
            % {"code": transfer.origin.code},
            field="code",
        )
    services.remove_accessories(
        item.accessory_model,
        quantity,
        user=user,
        container=container,
        location=None if container is not None else location,
        condition=item.condition,
        kind=EventKind.PICKING,
        document_ref=transfer.ref,
        reason=transfer.code,
    )
    _mark_picked(item, user, quantity=quantity)
    _start_picking(transfer)
    return item


# --- Files -------------------------------------------------------------------------------------


def add_file(transfer: Transfer, *, kind: str, upload, user) -> TransferFile:
    if transfer.status == TransferStatus.CANCELLED:
        raise DomainError(_("This transfer was cancelled."), field="transfer")
    if kind not in TransferFileKind.values:
        raise DomainError(_("Choose the kind of file."), field="kind")
    name = clean_filename(upload.name or "")
    errors = check_document(
        name, upload.size, settings.PRICE_DOCUMENT_MAX_MB * 1024 * 1024, attachment_messages()
    )
    if errors:
        raise DomainError(" ".join(str(e) for e in errors), field="file")
    item = TransferFile(
        transfer=transfer,
        kind=kind,
        name=name,
        size=upload.size,
        content_type=content_type_for(name),
        uploaded_by=user,
    )
    item.file.save(name, upload, save=False)
    item.save()
    return item


def remove_file(item: TransferFile) -> None:
    status = Transfer.objects.values_list("status", flat=True).get(pk=item.transfer_id)
    if status not in BEFORE_SENDING and item.kind == TransferFileKind.FISCAL_DOCUMENT:
        raise DomainError(_("The fiscal document of a sent transfer is kept."), field="file")
    item.delete()


# --- Sending -----------------------------------------------------------------------------------


def problems(transfer: Transfer) -> list[str]:
    """What still keeps the transfer from being sent (shown on its page)."""
    found = []
    if transfer.status == TransferStatus.REQUESTED:
        found.append(_("A supervisor must approve the transfer."))
    items = list(transfer.items.select_related("asset__current_location", "container"))
    if not items:
        found.append(_("Add the assets or accessories to transfer."))
    unpicked = [i for i in items if not i.picked]
    if unpicked:
        found.append(
            _("%(count)d item(s) not picked yet: read each one against the list.")
            % {"count": len(unpicked)}
        )
    for item in items:
        asset = item.asset
        if asset is None or not item.picked:
            continue
        try:
            _check_eligible(transfer, asset, adding=False)
        except DomainError as exc:
            found.append(str(exc.message))
            continue
        if item.container_id and asset.current_container_id != item.container_id:
            found.append(
                _("%(asset)s left container %(container)s: pick it again.")
                % {"asset": asset.horizon_id, "container": item.container.code}
            )
    if not transfer.fiscal_document_number.strip():
        found.append(_("Enter the fiscal document's number."))
    if not transfer.files.filter(kind=TransferFileKind.FISCAL_DOCUMENT).exists():
        found.append(_("Attach the fiscal document."))
    return found


@transaction.atomic
def send(transfer: Transfer, *, user) -> Transfer:
    """Everything picked (RN-24) and the fiscal document: the assets go in transit (keeping
    their status), containers with them, accessories leave the origin."""
    transfer = _lock(transfer, TransferStatus.APPROVED, TransferStatus.PICKING)
    found = problems(transfer)
    if found:
        raise DomainError(" ".join(str(p) for p in found), field="transfer")
    containers = {}
    for item in transfer.items.select_related("asset", "accessory_model", "container"):
        if item.asset_id:
            item.status_before = item.asset.status
            item.save(update_fields=["status_before"])
            services.transfer_out(
                item.asset,
                user=user,
                document_ref=transfer.ref,
                reason=transfer.code,
                container=item.container,
            )
            if item.container_id:
                containers[item.container_id] = item.container
        else:
            MovementEvent.objects.create(
                kind=EventKind.TRANSFER_OUT,
                user=user,
                accessory_model=item.accessory_model,
                quantity=item.quantity,
                accessory_condition=item.condition,
                to_location=Location.transit(),
                document_ref=transfer.ref,
                reason=transfer.code,
            )
    for container in containers.values():
        services.place_container(
            container,
            location=Location.transit(),
            user=user,
            kind=EventKind.TRANSFER_OUT,
            document_ref=transfer.ref,
        )
    transfer.status = TransferStatus.IN_TRANSIT
    transfer.sent_by = user
    transfer.sent_at = timezone.now()
    transfer.save()
    return transfer


# --- Receiving at the destination --------------------------------------------------------------

RECEIVING = (TransferStatus.IN_TRANSIT, TransferStatus.RECEIVED_WITH_DISCREPANCY)


def _check_destination(transfer: Transfer, location: Location | None) -> Location:
    if location is None or location.warehouse_id != transfer.destination_id:
        raise DomainError(
            _("Read a location of warehouse %(code)s.") % {"code": transfer.destination.code},
            field="location",
        )
    return location


def _occurrence(transfer: Transfer, kind: str, *, user, **fields) -> Occurrence:
    return Occurrence.objects.create(transfer=transfer, kind=kind, created_by=user, **fields)


def _arrived(transfer: Transfer, item: TransferItem, *, user, location) -> None:
    item.received_quantity = item.picked_quantity if item.asset_id else item.received_quantity
    item.received_at = timezone.now()
    item.received_by = user
    item.received_location = location
    item.save(
        update_fields=["received_quantity", "received_at", "received_by", "received_location"]
    )
    # Arrived after the receipt was finished: its shortage is resolved
    if item.asset_id:
        Occurrence.objects.filter(
            transfer=transfer,
            asset_id=item.asset_id,
            kind=OccurrenceKind.SHORTAGE,
            status=OccurrenceStatus.OPEN,
        ).update(
            status=OccurrenceStatus.RESOLVED,
            resolution=_("Arrived later."),
            resolved_by=user,
            resolved_at=timezone.now(),
        )


def _damage(transfer, asset, *, user, damaged: bool, note: str) -> None:
    if damaged:
        _occurrence(
            transfer,
            OccurrenceKind.TRANSPORT_DAMAGE,
            user=user,
            asset=asset,
            description=note.strip(),
        )


def receive(
    transfer: Transfer, target, *, location: Location, user, damaged: bool = False, note: str = ""
) -> list[TransferItem]:
    """An asset or a container read at the destination, after the location: back to the status
    it left in, there (RN-02). A container arrives with its assets. An asset not on the list is
    recorded as a surplus (and refused)."""
    surplus = None
    with transaction.atomic():
        transfer = _lock(transfer, *RECEIVING)
        _check_destination(transfer, location)
        if isinstance(target, Container):
            items = list(
                TransferItem.objects.select_for_update(of=("self",))
                .filter(transfer=transfer, container=target, received_quantity=0)
                .select_related("asset")
            )
            if not items:
                raise DomainError(
                    _("Container %(code)s has nothing of this transfer to receive.")
                    % {"code": target.code},
                    field="code",
                )
            services.place_container(
                target,
                location=location,
                user=user,
                kind=EventKind.TRANSFER_IN,
                document_ref=transfer.ref,
            )
            for item in items:
                services.transfer_in(
                    item.asset,
                    user=user,
                    location=location,
                    document_ref=transfer.ref,
                    reason=transfer.code,
                    container=target,
                )
                _arrived(transfer, item, user=user, location=location)
                _damage(transfer, item.asset, user=user, damaged=damaged, note=note)
            return items
        item = (
            TransferItem.objects.select_for_update().filter(transfer=transfer, asset=target).first()
        )
        if item is None:
            if not Occurrence.objects.filter(
                transfer=transfer, asset=target, kind=OccurrenceKind.SURPLUS
            ).exists():
                _occurrence(
                    transfer,
                    OccurrenceKind.SURPLUS,
                    user=user,
                    asset=target,
                    received_serial=target.serial,
                )
            surplus = target
        else:
            if item.received_quantity:
                raise DomainError(
                    _("%(asset)s was already received.") % {"asset": target.horizon_id},
                    field="code",
                )
            services.transfer_in(
                target,
                user=user,
                location=location,
                document_ref=transfer.ref,
                reason=transfer.code,
            )
            _arrived(transfer, item, user=user, location=location)
            _damage(transfer, target, user=user, damaged=damaged, note=note)
            return [item]
    # Outside the transaction: the surplus stays recorded
    raise DomainError(
        _("%(asset)s is not in this transfer: recorded as a surplus.")
        % {"asset": surplus.horizon_id},
        field="code",
    )


@transaction.atomic
def receive_accessory(
    transfer: Transfer,
    item: TransferItem,
    quantity: int,
    *,
    user,
    container: Container | None = None,
    location: Location | None = None,
) -> TransferItem:
    transfer = _lock(transfer, *RECEIVING)
    item = TransferItem.objects.select_for_update().get(pk=item.pk, transfer=transfer)
    if item.accessory_model_id is None:
        raise DomainError(_("Read the asset's ID."), field="item")
    left = item.picked_quantity - item.received_quantity
    if quantity < 1 or quantity > left:
        raise DomainError(_("Only %(left)d left to receive.") % {"left": left}, field="quantity")
    place = container.current_location if container is not None else location
    _check_destination(transfer, place)
    services.add_accessories(
        item.accessory_model,
        quantity,
        user=user,
        container=container,
        location=None if container is not None else location,
        condition=item.condition,
        kind=EventKind.TRANSFER_IN,
        document_ref=transfer.ref,
        reason=transfer.code,
    )
    item.received_quantity += quantity
    item.received_at = timezone.now()
    item.received_by = user
    item.received_location = place
    item.save(
        update_fields=["received_quantity", "received_at", "received_by", "received_location"]
    )
    return item


@transaction.atomic
def finish(transfer: Transfer, *, user) -> Transfer:
    """The receipt is over: what did not arrive is a shortage (the assets stay in transit until
    found); with any occurrence the transfer is received with discrepancy."""
    transfer = _lock(transfer, TransferStatus.IN_TRANSIT)
    for item in transfer.items.select_related("asset", "accessory_model"):
        missing = item.quantity - item.received_quantity
        if missing <= 0:
            continue
        if item.asset_id:
            _occurrence(
                transfer,
                OccurrenceKind.SHORTAGE,
                user=user,
                asset=item.asset,
                asset_model=item.asset.asset_model,
                expected_serial=item.asset.serial,
            )
        else:
            _occurrence(
                transfer,
                OccurrenceKind.SHORTAGE,
                user=user,
                asset_model=item.accessory_model,
                quantity=missing,
            )
    transfer.status = (
        TransferStatus.RECEIVED_WITH_DISCREPANCY
        if transfer.occurrences.exists()
        else TransferStatus.RECEIVED
    )
    transfer.received_by = user
    transfer.received_at = timezone.now()
    transfer.save()
    return transfer


@transaction.atomic
def cancel(transfer: Transfer, *, user, reason: str) -> Transfer:
    """Before sending: picked accessories return to their balance (assets never moved)."""
    if not reason.strip():
        raise DomainError(_("Say why the transfer is cancelled."), field="reason")
    transfer = _lock(transfer, *BEFORE_SENDING)
    back = _("Cancelled: %(code)s") % {"code": transfer.code}
    for event in MovementEvent.objects.filter(
        kind=EventKind.PICKING, document_ref=transfer.ref, accessory_model__isnull=False
    ).select_related("from_container", "from_location", "accessory_model"):
        services.add_accessories(
            event.accessory_model,
            event.quantity,
            user=user,
            container=event.from_container,
            location=None if event.from_container_id else event.from_location,
            condition=event.accessory_condition or AccessoryCondition.GOOD,
            kind=EventKind.REVERSAL,
            document_ref=transfer.ref,
            reason=back,
        )
    transfer.status = TransferStatus.CANCELLED
    transfer.cancelled_by = user
    transfer.cancelled_at = timezone.now()
    transfer.cancel_reason = reason.strip()
    transfer.save()
    return transfer


def days_late(transfer: Transfer, today) -> int:
    """Days beyond the transit days (0 when on time or not in transit)."""
    if transfer.status != TransferStatus.IN_TRANSIT or transfer.sent_at is None:
        return 0
    days = (today - timezone.localtime(transfer.sent_at).date()).days
    return max(days - transfer.transit_days, 0)
