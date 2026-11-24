"""Inventory operations. The **only** code that changes an asset's status, location or container
(RN-07): each operation runs in one transaction, locks what it changes (`select_for_update`) and
records its movement event(s). Business rules come from inventory.states (RN-01, RN-02) and
inventory.codes (RN-15); refusals raise states.DomainError with a translated message.
"""

import re

from django.db import connection, transaction
from django.utils.translation import gettext as _

from catalogs.models import Tracking
from catalogs.serializers import spec_messages
from catalogs.specs import SpecError, snapshot_values

from .codes import ASSET_PREFIX, CONTAINER_PREFIX, format_code, parse_code
from .models import (
    AccessoryBalance,
    AccessoryCondition,
    Asset,
    Container,
    EventKind,
    LabelRange,
    Location,
    MovementEvent,
    NoSerialReason,
    SerialStatus,
)
from .states import AreaType, AssetStatus, DomainError, check_area, check_transition

HORIZON_ID_SEQUENCE = "inventory_horizon_id_seq"
CONTAINER_SEQUENCE = "inventory_container_code_seq"
MAX_LABEL_RANGE = 1000


# --- Codes -----------------------------------------------------------------------------------


def _lock_sequence(sequence: str) -> None:
    """Serialize the use of a sequence inside the transaction (contiguous label ranges)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [sequence])


def _next_numbers(sequence: str, count: int = 1) -> int:
    """Take `count` consecutive numbers of a sequence; returns the first one."""
    _lock_sequence(sequence)
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s)", [sequence])
        first = cursor.fetchone()[0]
        if count > 1:
            cursor.execute("SELECT setval(%s, %s)", [sequence, first + count - 1])
    return first


@transaction.atomic
def new_horizon_id() -> str:
    return format_code(ASSET_PREFIX, _next_numbers(HORIZON_ID_SEQUENCE))


@transaction.atomic
def reserve_label_range(count: int, user) -> LabelRange:
    """Reserve `count` consecutive Horizon IDs to print their labels in advance."""
    if not 1 <= count <= MAX_LABEL_RANGE:
        raise DomainError(
            _("Reserve from 1 to %(max)d labels at a time.") % {"max": MAX_LABEL_RANGE},
            field="count",
        )
    first = _next_numbers(HORIZON_ID_SEQUENCE, count)
    return LabelRange.objects.create(
        first_number=first, last_number=first + count - 1, reserved_by=user
    )


def _check_reserved_id(horizon_id: str) -> str:
    """A pre-printed label read at entry: valid, from a reserved range, never used (RN-15)."""
    parsed = parse_code(horizon_id)
    if parsed.kind != "asset" or not parsed.valid:
        raise DomainError(_("This is not a valid Horizon ID."), field="horizon_id")
    reserved = LabelRange.objects.filter(
        first_number__lte=parsed.number, last_number__gte=parsed.number
    ).exists()
    if not reserved:
        raise DomainError(_("This Horizon ID was not reserved for printing."), field="horizon_id")
    if Asset.objects.filter(horizon_id=parsed.code).exists():
        raise DomainError(_("This Horizon ID is already in use."), field="horizon_id")
    return parsed.code


# --- Reading codes -----------------------------------------------------------------------------


def resolve_code(text: str, *, field: str = "code"):
    """The asset, container or location of a code read by a gun (check digit verified)."""
    parsed = parse_code(text)
    if not parsed.valid:
        message = (
            _("Wrong check digit: read the label again.")
            if parsed.kind in ("asset", "container")
            else _("Unknown code.")
        )
        raise DomainError(message, field=field)
    model = {"asset": Asset, "container": Container, "location": Location}[parsed.kind]
    lookup = "horizon_id" if parsed.kind == "asset" else "code"
    found = model.objects.filter(**{lookup: parsed.code}).first()
    if found is None:
        raise DomainError(
            _("Nothing is registered with code %(code)s.") % {"code": parsed.code}, field=field
        )
    return found


# --- Events ----------------------------------------------------------------------------------


# Events that change nothing physical (or are the count's own adjustments)
NOT_BLOCKED_BY_COUNTS = (EventKind.LABEL_REPRINT, EventKind.INVENTORY_ADJUSTMENT)


def check_not_counting(*locations) -> None:
    """While a count is open, nothing moves in or out of its locations (decision)."""
    from .models import CountStatus, InventoryCount

    ids = {loc.pk for loc in locations if loc is not None}
    if not ids:
        return
    count = InventoryCount.objects.filter(status=CountStatus.COUNTING, locations__in=ids).first()
    if count is not None:
        raise DomainError(
            _("Location being counted (%(code)s): nothing moves there until the count closes.")
            % {"code": count.code},
            field="destination",
        )


def _record(kind, *, user, asset=None, container=None, **fields) -> MovementEvent:
    if kind not in NOT_BLOCKED_BY_COUNTS:
        check_not_counting(fields.get("from_location"), fields.get("to_location"))
    return MovementEvent.objects.create(
        kind=kind, user=user, asset=asset, container=container, **fields
    )


def _check_place(location: Location, *, allow_virtual: bool = False):
    if not location.is_active:
        raise DomainError(_("This location is inactive."), field="destination")
    if location.is_virtual and not allow_virtual:
        raise DomainError(_("Assets go in transit only through a transfer."), field="destination")


# --- Assets ----------------------------------------------------------------------------------


@transaction.atomic
def register_entry(
    *,
    asset_model,
    location: Location,
    user,
    serial: str = "",
    no_serial_reason: str = "",
    other_ids: dict | None = None,
    specs: dict | None = None,
    container: Container | None = None,
    horizon_id: str = "",
    reason: str = "",
    document_ref: str = "",
    lot=None,
    customer=None,
) -> Asset:
    """An asset arrives (triage of a receiving lot): IN_TRIAGE at a dock, with its Horizon ID —
    a pre-printed one read from its label, or a new one."""
    if asset_model.tracking != Tracking.UNIT:
        raise DomainError(
            _("Models controlled by quantity have no units with their own ID."),
            field="asset_model",
        )
    serial = "".join((serial or "").split()).upper()
    if serial:
        serial_status, no_serial_reason = SerialStatus.CAPTURED, ""
        if asset_model.serial_regex and not re.fullmatch(asset_model.serial_regex, serial):
            raise DomainError(
                _("This serial number does not match the model's pattern."), field="serial"
            )
        if Asset.objects.filter(
            asset_model=asset_model, serial=serial, serial_status=SerialStatus.CAPTURED
        ).exists():  # RN-05 (the database constraint also guards it)
            raise DomainError(
                _("An asset of this model with this serial number already exists."),
                field="serial",
            )
    else:
        if no_serial_reason not in NoSerialReason.values:
            raise DomainError(
                _("Read the serial number or say why it cannot be read."), field="serial"
            )
        serial_status = (
            SerialStatus.PENDING
            if no_serial_reason == NoSerialReason.NEEDS_POWER_ON
            else SerialStatus.NONE
        )

    if container is not None:
        container = Container.objects.select_for_update().get(pk=container.pk)
        if not container.is_active:
            raise DomainError(_("This container is inactive."), field="container")
        location = container.current_location
    location = Location.objects.select_for_update().get(pk=location.pk)
    _check_place(location)
    check_area(location.area_type, AssetStatus.IN_TRIAGE)

    template = asset_model.asset_class.spec_template
    if specs is None:  # the model's values
        specs = {field["key"]: field["value"] for field in asset_model.specs}
    try:
        # Required fields are completed at inspection: at entry every one is optional
        optional = [{**field, "required": False} for field in template]
        snapshot = snapshot_values(optional, specs, spec_messages())
    except SpecError as exc:
        raise DomainError(_("Check the specification values."), field="specs") from exc
    required = {f["key"]: f["required"] for f in template}
    snapshot = [{**f, "required": required[f["key"]]} for f in snapshot]

    asset = Asset.objects.create(
        horizon_id=_check_reserved_id(horizon_id) if horizon_id else new_horizon_id(),
        asset_model=asset_model,
        specs=snapshot,
        serial=serial,
        serial_status=serial_status,
        no_serial_reason=no_serial_reason,
        other_ids=other_ids or {},
        status=AssetStatus.IN_TRIAGE,
        current_location=location,
        current_container=container,
        lot=lot,
        customer=customer,
        created_by=user,
    )
    _record(
        EventKind.ENTRY,
        user=user,
        asset=asset,
        to_location=location,
        to_container=container,
        status_after=AssetStatus.IN_TRIAGE,
        reason=reason,
        document_ref=document_ref,
    )
    return asset


@transaction.atomic
def move_asset(
    asset: Asset,
    *,
    user,
    to_location: Location | None = None,
    to_container: Container | None = None,
    reason: str = "",
    kind: str = EventKind.RELOCATION,
    document_ref: str = "",
) -> MovementEvent:
    """Move an asset to a location (leaving any container) or into a container (where the
    container is). The destination's area must take the asset's status (RN-02)."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    if asset.status == AssetStatus.WRITTEN_OFF:
        raise DomainError(_("This asset has left the stock."), field="object")
    if asset.status == AssetStatus.IN_TRANSIT:
        raise DomainError(_("This asset is in transit between warehouses."), field="object")
    if to_container is not None:
        to_container = Container.objects.select_for_update().get(pk=to_container.pk)
        if not to_container.is_active:
            raise DomainError(_("This container is inactive."), field="destination")
        to_location = to_container.current_location
    if to_location is None:
        raise DomainError(_("Read the destination."), field="destination")
    _check_place(to_location)
    if to_location == asset.current_location and to_container == asset.current_container:
        raise DomainError(_("The asset is already there."), field="destination")
    check_area(to_location.area_type, asset.status, held_for_dispute=asset.held_for_dispute)

    event = _record(
        kind,
        user=user,
        asset=asset,
        from_location=asset.current_location,
        to_location=to_location,
        from_container=asset.current_container,
        to_container=to_container,
        status_before=asset.status,
        status_after=asset.status,
        reason=reason,
        document_ref=document_ref,
    )
    asset.current_location = to_location
    asset.current_container = to_container
    asset.save(update_fields=["current_location", "current_container", "updated_at"])
    return event


@transaction.atomic
def move_container(
    container: Container, *, to_location: Location, user, reason: str = ""
) -> MovementEvent:
    """Move a container with everything inside: one event for the container and one child
    event per asset in it, so each asset's history is complete (RN-08). Every asset inside
    must fit the destination (RN-02), or nothing moves."""
    container = Container.objects.select_for_update().get(pk=container.pk)
    if not container.is_active:
        raise DomainError(_("This container is inactive."), field="object")
    if container.current_location.is_virtual:
        raise DomainError(_("This container is in transit between warehouses."), field="object")
    _check_place(to_location)
    if to_location == container.current_location:
        raise DomainError(_("The container is already there."), field="destination")
    assets = list(Asset.objects.select_for_update().filter(current_container=container))
    for asset in assets:
        try:
            check_area(to_location.area_type, asset.status, held_for_dispute=asset.held_for_dispute)
        except DomainError as exc:
            raise DomainError(
                _("%(asset)s cannot go there: %(reason)s")
                % {"asset": asset.horizon_id, "reason": exc.message},
                field="destination",
            ) from exc

    parent = _record(
        EventKind.RELOCATION,
        user=user,
        container=container,
        from_location=container.current_location,
        to_location=to_location,
        reason=reason,
    )
    for asset in assets:
        _record(
            EventKind.RELOCATION,
            user=user,
            asset=asset,
            from_location=asset.current_location,
            to_location=to_location,
            from_container=container,
            to_container=container,
            status_before=asset.status,
            status_after=asset.status,
            reason=reason,
            parent_event=parent,
        )
        asset.current_location = to_location
        asset.save(update_fields=["current_location", "updated_at"])
    container.current_location = to_location
    container.save(update_fields=["current_location", "updated_at"])
    return parent


@transaction.atomic
def change_status(
    asset: Asset,
    *,
    to_status: str,
    user,
    reason: str = "",
    document_ref: str = "",
    to_location: Location | None = None,
    kind: str = EventKind.STATUS_CHANGE,
) -> MovementEvent:
    """Change an asset's status (RN-01), optionally moving it at the same time (then the
    destination must take the new status — RN-02). Going in transit keeps the status to come
    back to; leaving transit only returns to it."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    before = asset.status
    check_transition(before, to_status, status_before_transit=asset.status_before_transit or None)
    if to_status == AssetStatus.IN_TRANSIT:
        to_location = Location.transit()
    if to_location is not None:
        _check_place(to_location, allow_virtual=to_status == AssetStatus.IN_TRANSIT)
        check_area(to_location.area_type, to_status, held_for_dispute=asset.held_for_dispute)

    event = _record(
        kind,
        user=user,
        asset=asset,
        from_location=asset.current_location,
        to_location=to_location or asset.current_location,
        from_container=asset.current_container,
        to_container=None if to_location else asset.current_container,
        status_before=before,
        status_after=to_status,
        reason=reason,
        document_ref=document_ref,
    )
    asset.status = to_status
    asset.status_before_transit = before if to_status == AssetStatus.IN_TRANSIT else ""
    if to_location is not None:
        asset.current_location = to_location
        asset.current_container = None
    asset.save(
        update_fields=[
            "status",
            "status_before_transit",
            "current_location",
            "current_container",
            "updated_at",
        ]
    )
    return event


@transaction.atomic
def reverse_event(event: MovementEvent, *, user, reason: str) -> MovementEvent:
    """Undo an asset's latest event with a REVERSAL event (events are never changed): the
    asset goes back to where it was, in the status it had."""
    if not reason.strip():
        raise DomainError(_("Say why the event is reversed."), field="reason")
    if event.asset_id is None or event.parent_event_id is not None:
        raise DomainError(_("Only an asset's own events can be reversed."), field="event")
    if event.kind in (EventKind.ENTRY, EventKind.REVERSAL, EventKind.LABEL_REPRINT):
        raise DomainError(_("This event cannot be reversed."), field="event")
    if event.document_ref.startswith("transfer:"):
        raise DomainError(
            _("Events of a transfer are undone by the transfer (cancel it before sending)."),
            field="event",
        )
    if event.document_ref.startswith("disposal:"):
        raise DomainError(
            _("Events of a disposal are undone by the disposal (remove the item or cancel it)."),
            field="event",
        )
    asset = Asset.objects.select_for_update().get(pk=event.asset_id)
    latest = asset.events.exclude(kind=EventKind.LABEL_REPRINT).order_by("-at", "-id").first()
    if latest != event:
        raise DomainError(_("Only the asset's latest event can be reversed."), field="event")
    back_to = event.from_location
    if back_to is None or (back_to.area_type == AreaType.VIRTUAL_TRANSIT):
        raise DomainError(_("This event cannot be reversed."), field="event")

    reversal = _record(
        EventKind.REVERSAL,
        user=user,
        asset=asset,
        from_location=asset.current_location,
        to_location=back_to,
        from_container=asset.current_container,
        to_container=event.from_container,
        status_before=asset.status,
        status_after=event.status_before or asset.status,
        reason=reason,
        reverses=event,
    )
    asset.current_location = back_to
    asset.current_container = event.from_container
    asset.status = event.status_before or asset.status
    asset.save(update_fields=["current_location", "current_container", "status", "updated_at"])
    return reversal


@transaction.atomic
def reprint_label(target, *, user, reason: str = "") -> MovementEvent:
    """An asset's or container's label printed again: always the same code, never a new one
    (RN-16); recorded as an event."""
    if isinstance(target, Asset):
        return _record(
            EventKind.LABEL_REPRINT,
            user=user,
            asset=target,
            status_before=target.status,
            status_after=target.status,
            reason=reason,
        )
    return _record(EventKind.LABEL_REPRINT, user=user, container=target, reason=reason)


# --- Containers --------------------------------------------------------------------------------


@transaction.atomic
def create_container(*, kind: str, location: Location, user, description: str = "") -> Container:
    location = Location.objects.select_for_update().get(pk=location.pk)
    _check_place(location)
    container = Container.objects.create(
        code=format_code(CONTAINER_PREFIX, _next_numbers(CONTAINER_SEQUENCE)),
        kind=kind,
        current_location=location,
        description=description,
    )
    _record(EventKind.ENTRY, user=user, container=container, to_location=location)
    return container


# --- Accessory balances (models tracked by quantity) ----------------------------------------


def _balance(asset_model, *, container=None, location=None, condition) -> AccessoryBalance:
    """The balance row, locked (created at zero when missing)."""
    place = {"container": container} if container is not None else {"location": location}
    balance, _created = AccessoryBalance.objects.select_for_update().get_or_create(
        asset_model=asset_model, condition=condition, **place
    )
    return balance


@transaction.atomic
def add_accessories(
    asset_model,
    quantity: int,
    *,
    user,
    container: Container | None = None,
    location: Location | None = None,
    condition: str = AccessoryCondition.GOOD,
    kind: str = EventKind.ENTRY,
    reason: str = "",
    document_ref: str = "",
) -> MovementEvent:
    """Units of an accessory model enter a container or a location (an event records it)."""
    if asset_model.tracking != Tracking.QUANTITY:
        raise DomainError(
            _("Only models controlled by quantity have balances."), field="asset_model"
        )
    if quantity < 1:
        raise DomainError(_("Enter a quantity of at least 1."), field="quantity")
    if container is not None:
        container = Container.objects.select_for_update().get(pk=container.pk)
        if not container.is_active:
            raise DomainError(_("This container is inactive."), field="container")
        place = container.current_location
    elif location is not None:
        place = location
    else:
        raise DomainError(_("Read the destination."), field="destination")
    _check_place(place)
    balance = _balance(
        asset_model,
        container=container,
        location=None if container else location,
        condition=condition,
    )
    balance.quantity += quantity
    balance.save(update_fields=["quantity", "updated_at"])
    return _record(
        kind,
        user=user,
        accessory_model=asset_model,
        quantity=quantity,
        accessory_condition=condition,
        to_location=place,
        to_container=container,
        reason=reason,
        document_ref=document_ref,
    )


@transaction.atomic
def remove_accessories(
    asset_model,
    quantity: int,
    *,
    user,
    container: Container | None = None,
    location: Location | None = None,
    condition: str = AccessoryCondition.GOOD,
    kind: str = EventKind.PICKING,
    reason: str = "",
    document_ref: str = "",
) -> MovementEvent:
    """Units of an accessory model leave a container or a location; a balance never goes
    below zero (RN-06)."""
    if quantity < 1:
        raise DomainError(_("Enter a quantity of at least 1."), field="quantity")
    balance = _balance(
        asset_model,
        container=container,
        location=None if container else location,
        condition=condition,
    )
    if balance.quantity < quantity:
        raise DomainError(
            _("Only %(available)d available here.") % {"available": balance.quantity},
            field="quantity",
        )
    balance.quantity -= quantity
    balance.save(update_fields=["quantity", "updated_at"])
    return _record(
        kind,
        user=user,
        accessory_model=asset_model,
        quantity=quantity,
        accessory_condition=condition,
        from_location=balance.place,
        from_container=container,
        reason=reason,
        document_ref=document_ref,
    )


# --- Children of an asset (a removed disk, harvested parts) ----------------------------------


@transaction.atomic
def register_child(
    parent: Asset,
    *,
    asset_model,
    user,
    status: str,
    serial: str = "",
    reason: str = "",
    document_ref: str = "",
) -> Asset:
    """A unit taken out of an asset (a disk removed for destruction, a harvested part): a new
    asset pointing to its parent, where the parent is, in `status`, with its entry event."""
    if asset_model.tracking != Tracking.UNIT:
        raise DomainError(
            _("Models controlled by quantity have no units with their own ID."),
            field="asset_model",
        )
    serial = "".join((serial or "").split()).upper()
    if (
        serial
        and Asset.objects.filter(
            asset_model=asset_model, serial=serial, serial_status=SerialStatus.CAPTURED
        ).exists()
    ):
        raise DomainError(
            _("An asset of this model with this serial number already exists."), field="serial"
        )
    template = asset_model.asset_class.spec_template
    required = {f["key"]: f["required"] for f in template}
    try:
        snapshot = snapshot_values(
            [{**f, "required": False} for f in template],
            {f["key"]: f["value"] for f in asset_model.specs},
            spec_messages(),
        )
    except SpecError:
        snapshot = []
    child = Asset.objects.create(
        horizon_id=new_horizon_id(),
        asset_model=asset_model,
        specs=[{**f, "required": required.get(f["key"], False)} for f in snapshot],
        serial=serial,
        serial_status=SerialStatus.CAPTURED if serial else SerialStatus.NONE,
        no_serial_reason="" if serial else NoSerialReason.UNREADABLE,
        status=status,
        current_location=parent.current_location,
        parent_asset=parent,
        lot=parent.lot,
        customer=parent.customer,
        created_by=user,
    )
    _record(
        EventKind.ENTRY,
        user=user,
        asset=child,
        to_location=child.current_location,
        status_after=status,
        reason=reason,
        document_ref=document_ref,
    )
    return child


# --- Transfers between warehouses (Phase 6) ------------------------------------------------


@transaction.atomic
def transfer_out(
    asset: Asset, *, user, document_ref: str, reason: str = "", container: Container | None = None
) -> MovementEvent:
    """The asset leaves its warehouse: IN_TRANSIT at the virtual location, keeping the status
    it comes back to (and the container it travels in, if any)."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    check_transition(asset.status, AssetStatus.IN_TRANSIT)
    transit = Location.transit()
    event = _record(
        EventKind.TRANSFER_OUT,
        user=user,
        asset=asset,
        from_location=asset.current_location,
        to_location=transit,
        from_container=asset.current_container,
        to_container=container,
        status_before=asset.status,
        status_after=AssetStatus.IN_TRANSIT,
        reason=reason,
        document_ref=document_ref,
    )
    asset.status_before_transit = asset.status
    asset.status = AssetStatus.IN_TRANSIT
    asset.current_location = transit
    asset.current_container = container
    asset.save(
        update_fields=[
            "status",
            "status_before_transit",
            "current_location",
            "current_container",
            "updated_at",
        ]
    )
    return event


@transaction.atomic
def transfer_in(
    asset: Asset,
    *,
    user,
    location: Location,
    document_ref: str,
    reason: str = "",
    container: Container | None = None,
) -> MovementEvent:
    """The asset arrives: back to the status it left in, at `location` (or in `container`,
    there) — the area must take that status (RN-02)."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    if asset.status != AssetStatus.IN_TRANSIT:
        raise DomainError(_("This asset is not in transit."), field="code")
    back = asset.status_before_transit
    check_transition(asset.status, back, status_before_transit=back)
    _check_place(location)
    check_area(location.area_type, back, held_for_dispute=asset.held_for_dispute)
    event = _record(
        EventKind.TRANSFER_IN,
        user=user,
        asset=asset,
        from_location=asset.current_location,
        to_location=location,
        from_container=asset.current_container,
        to_container=container,
        status_before=AssetStatus.IN_TRANSIT,
        status_after=back,
        reason=reason,
        document_ref=document_ref,
    )
    asset.status = back
    asset.status_before_transit = ""
    asset.current_location = location
    asset.current_container = container
    asset.save(
        update_fields=[
            "status",
            "status_before_transit",
            "current_location",
            "current_container",
            "updated_at",
        ]
    )
    return event


@transaction.atomic
def place_container(
    container: Container, *, location: Location, user, kind: str, document_ref: str = ""
) -> MovementEvent:
    """A container travelling between warehouses (to the virtual location and back to a real
    one); its assets are moved by transfer_out / transfer_in."""
    container = Container.objects.select_for_update().get(pk=container.pk)
    event = _record(
        kind,
        user=user,
        container=container,
        from_location=container.current_location,
        to_location=location,
        document_ref=document_ref,
    )
    container.current_location = location
    container.save(update_fields=["current_location", "updated_at"])
    return event


# --- Inventory adjustments (Phase 7) ----------------------------------------------------------


@transaction.atomic
def adjust_lost(asset: Asset, *, user, document_ref: str, reason: str) -> MovementEvent:
    """An asset not found in a count, its adjustment approved: written off as lost (outside
    the transition table — an inventory adjustment)."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    event = _record(
        EventKind.INVENTORY_ADJUSTMENT,
        user=user,
        asset=asset,
        from_location=asset.current_location,
        to_location=asset.current_location,
        from_container=asset.current_container,
        status_before=asset.status,
        status_after=AssetStatus.WRITTEN_OFF,
        reason=reason,
        document_ref=document_ref,
    )
    asset.status = AssetStatus.WRITTEN_OFF
    asset.current_container = None
    asset.save(update_fields=["status", "current_container", "updated_at"])
    return event


@transaction.atomic
def adjust_place(
    asset: Asset,
    *,
    location: Location,
    user,
    document_ref: str,
    reason: str,
    status: str | None = None,
) -> MovementEvent:
    """An asset counted somewhere else than recorded: the records follow what was found (the
    count is the truth; RN-02 is not applied). `status` brings back an asset written off as
    lost by an earlier count."""
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    after = status or asset.status
    event = _record(
        EventKind.INVENTORY_ADJUSTMENT,
        user=user,
        asset=asset,
        from_location=asset.current_location,
        to_location=location,
        from_container=asset.current_container,
        status_before=asset.status,
        status_after=after,
        reason=reason,
        document_ref=document_ref,
    )
    asset.status = after
    asset.current_location = location
    asset.current_container = None
    asset.save(update_fields=["status", "current_location", "current_container", "updated_at"])
    return event


@transaction.atomic
def adjust_balance(
    asset_model,
    *,
    counted: int,
    user,
    document_ref: str,
    reason: str,
    condition: str,
    container: Container | None = None,
    location: Location | None = None,
) -> MovementEvent | None:
    """An accessory balance set to what was counted (the difference as one event)."""
    balance = _balance(
        asset_model,
        container=container,
        location=None if container else location,
        condition=condition,
    )
    difference = counted - balance.quantity
    if difference == 0:
        return None
    balance.quantity = counted
    balance.save(update_fields=["quantity", "updated_at"])
    place = balance.place
    return _record(
        EventKind.INVENTORY_ADJUSTMENT,
        user=user,
        accessory_model=asset_model,
        quantity=abs(difference),
        accessory_condition=condition,
        from_location=None if difference > 0 else place,
        to_location=place if difference > 0 else None,
        from_container=None if difference > 0 else container,
        to_container=container if difference > 0 else None,
        reason=reason,
        document_ref=document_ref,
    )
