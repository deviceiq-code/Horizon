"""Disposals (Phase 5): the way out of the stock. The only code that changes a disposal; asset
statuses and places still change only through inventory.services (RN-07).

create → add assets (AVAILABLE → RESERVED; scrap assets join discards and stay SCRAP — decision)
and accessories (by quantity) → pick: read each ID against the list, moving it to a shipping
area; accessories read from their container or location → ship (document; a discard needs its
destination certificate — RN-23): assets written off, accessories leave → SHIPPED. Cancelling
gives everything back. An asset held for a dispute is never reserved nor shipped.
"""

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from catalogs.models import Tracking
from pricing.documents import check_document, clean_filename, content_type_for

from . import services
from .models import (
    CUSTOMER_KINDS,
    OPEN_DISPOSAL,
    AccessoryBalance,
    AccessoryCondition,
    Appointment,
    AppointmentKind,
    AppointmentStatus,
    Asset,
    Container,
    Disposal,
    DisposalFile,
    DisposalFileKind,
    DisposalItem,
    DisposalKind,
    DisposalStatus,
    EventKind,
    Location,
    MovementEvent,
)
from .receiving import attachment_messages, create_with_code
from .states import AreaType, AssetStatus, DomainError, area_accepts

# --- Header ----------------------------------------------------------------------------------


def check_header(
    *, kind: str, warehouse, customer=None, discard_provider=None, appointment=None
) -> None:
    """Who and what the disposal is for, by kind."""
    if kind not in DisposalKind.values or kind == DisposalKind.PARTS:
        raise DomainError(_("Choose the kind of disposal."), field="kind")
    if kind in CUSTOMER_KINDS and customer is None:
        message = (
            _("Choose the buyer (registered as a customer).")
            if kind == DisposalKind.THIRD_PARTY_SALE
            else _("Choose the customer.")
        )
        raise DomainError(message, field="customer")
    if kind == DisposalKind.DISCARD:
        if discard_provider is None:
            raise DomainError(
                _("Choose the provider that receives the discard."), field="discard_provider"
            )
        if not discard_provider.is_active or "disposal" not in (discard_provider.services or []):
            raise DomainError(
                _("Choose an active provider offering disposal."), field="discard_provider"
            )
    if appointment is not None:
        if appointment.kind != AppointmentKind.SHIPPING:
            raise DomainError(_("Choose a shipping appointment."), field="appointment")
        if appointment.warehouse_id != warehouse.pk:
            raise DomainError(_("The appointment is at another warehouse."), field="appointment")
        if appointment.status in (
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
            AppointmentStatus.DONE,
        ):
            raise DomainError(_("This appointment is closed."), field="appointment")


def create(
    *,
    kind: str,
    warehouse,
    user,
    customer=None,
    contract: str = "",
    discard_provider=None,
    appointment=None,
    notes: str = "",
    keywords=None,
) -> Disposal:
    check_header(
        kind=kind,
        warehouse=warehouse,
        customer=customer,
        discard_provider=discard_provider,
        appointment=appointment,
    )
    return create_with_code(
        Disposal,
        kind=kind,
        warehouse=warehouse,
        customer=customer if kind in CUSTOMER_KINDS else None,
        contract=contract.strip() if kind == DisposalKind.RELOCATION else "",
        discard_provider=discard_provider if kind == DisposalKind.DISCARD else None,
        appointment=appointment,
        notes=notes,
        keywords=keywords or [],
        created_by=user,
    )


def _lock_open(disposal: Disposal) -> Disposal:
    disposal = Disposal.objects.select_for_update().get(pk=disposal.pk)
    if disposal.status not in OPEN_DISPOSAL:
        raise DomainError(_("This disposal is closed."), field="disposal")
    return disposal


@transaction.atomic
def update_header(disposal: Disposal, **fields) -> Disposal:
    """Customer, contract, provider, appointment, document number, notes and keywords, while
    open (the kind and the warehouse never change)."""
    disposal = _lock_open(disposal)
    for name, value in fields.items():
        setattr(disposal, name, value)
    check_header(
        kind=disposal.kind,
        warehouse=disposal.warehouse,
        customer=disposal.customer,
        discard_provider=disposal.discard_provider,
        appointment=disposal.appointment,
    )
    if disposal.kind not in CUSTOMER_KINDS:
        disposal.customer = None
    if disposal.kind != DisposalKind.RELOCATION:
        disposal.contract = ""
    if disposal.kind != DisposalKind.DISCARD:
        disposal.discard_provider = None
    disposal.save()
    return disposal


# --- Items -------------------------------------------------------------------------------------


def open_disposal_of(asset: Asset) -> Disposal | None:
    """The open disposal an asset is in, if any."""
    item = (
        DisposalItem.objects.filter(asset=asset, disposal__status__in=OPEN_DISPOSAL)
        .select_related("disposal")
        .first()
    )
    return item.disposal if item else None


def check_not_in_disposal(asset: Asset) -> None:
    """For other operations on scrap assets (taking apart…)."""
    disposal = open_disposal_of(asset)
    if disposal is not None:
        raise DomainError(
            _("This asset is in disposal %(code)s.") % {"code": disposal.code}, field="asset"
        )


@transaction.atomic
def add_asset(disposal: Disposal, asset: Asset, *, user, unit_value: Decimal | None = None):
    """Reserve an asset for the disposal: AVAILABLE → RESERVED; a scrap asset joins a discard
    and stays SCRAP. Held for a dispute, elsewhere or in another status → refused."""
    disposal = _lock_open(disposal)
    asset = Asset.objects.select_for_update().select_related("current_location").get(pk=asset.pk)
    if asset.held_for_dispute:
        raise DomainError(
            _("%(asset)s is held for a dispute and cannot be reserved.")
            % {"asset": asset.horizon_id},
            field="asset",
        )
    if asset.current_location.warehouse_id != disposal.warehouse_id:
        raise DomainError(
            _("%(asset)s is at another warehouse.") % {"asset": asset.horizon_id}, field="asset"
        )
    from .transfers import check_not_in_transfer

    check_not_in_transfer(asset)
    other = open_disposal_of(asset)
    if other is not None:
        raise DomainError(
            _("%(asset)s is already in disposal %(code)s.")
            % {"asset": asset.horizon_id, "code": other.code},
            field="asset",
        )
    scrap_ok = disposal.kind == DisposalKind.DISCARD and asset.status == AssetStatus.SCRAP
    if asset.status != AssetStatus.AVAILABLE and not scrap_ok:
        message = _(
            "%(asset)s is %(status)s: only available assets are reserved "
            "(scrap ones only in discards)."
        )
        raise DomainError(
            message % {"asset": asset.horizon_id, "status": AssetStatus(asset.status).label},
            field="asset",
        )
    item = DisposalItem.objects.create(disposal=disposal, asset=asset, unit_value=unit_value)
    if asset.status == AssetStatus.AVAILABLE:
        services.change_status(
            asset,
            to_status=AssetStatus.RESERVED,
            user=user,
            document_ref=disposal.ref,
            reason=disposal.code,
        )
    return item


def reserved_quantity(asset_model, warehouse, condition, *, exclude_item=None) -> int:
    """Units of an accessory model in open disposals of a warehouse, not picked yet."""
    items = DisposalItem.objects.filter(
        accessory_model=asset_model,
        condition=condition,
        disposal__warehouse=warehouse,
        disposal__status__in=OPEN_DISPOSAL,
    )
    if exclude_item is not None:
        items = items.exclude(pk=exclude_item.pk)
    total = 0
    for quantity, picked in items.values_list("quantity", "picked_quantity"):
        total += quantity - picked
    return total


def stock_quantity(asset_model, warehouse, condition) -> int:
    """Units of an accessory model in a warehouse's balances."""
    balances = AccessoryBalance.objects.filter(asset_model=asset_model, condition=condition)
    in_place = balances.filter(location__warehouse=warehouse) | balances.filter(
        container__current_location__warehouse=warehouse
    )
    return in_place.aggregate(total=Sum("quantity"))["total"] or 0


@transaction.atomic
def add_accessory(
    disposal: Disposal,
    asset_model,
    quantity: int,
    *,
    user,
    condition: str = AccessoryCondition.GOOD,
    unit_value: Decimal | None = None,
) -> DisposalItem:
    """A quantity of an accessory model (good; scrap only in discards). The balances are taken
    at picking; here the warehouse must have them, minus what other disposals reserved."""
    disposal = _lock_open(disposal)
    if asset_model.tracking != Tracking.QUANTITY:
        raise DomainError(
            _("Only models controlled by quantity are added by quantity."), field="asset_model"
        )
    if quantity < 1:
        raise DomainError(_("Enter a quantity of at least 1."), field="quantity")
    if condition not in AccessoryCondition.values or (
        condition == AccessoryCondition.SCRAP and disposal.kind != DisposalKind.DISCARD
    ):
        raise DomainError(_("Scrap accessories only go in discards."), field="condition")
    free = stock_quantity(asset_model, disposal.warehouse, condition) - reserved_quantity(
        asset_model, disposal.warehouse, condition
    )
    if quantity > free:
        raise DomainError(
            _("Only %(available)d available in this warehouse.") % {"available": max(free, 0)},
            field="quantity",
        )
    return DisposalItem.objects.create(
        disposal=disposal,
        accessory_model=asset_model,
        quantity=quantity,
        condition=condition,
        unit_value=unit_value,
    )


@transaction.atomic
def set_unit_value(item: DisposalItem, value: Decimal | None) -> DisposalItem:
    _lock_open(item.disposal)
    if value is not None and value < 0:
        raise DomainError(_("The value cannot be negative."), field="unit_value")
    item.unit_value = value
    item.save(update_fields=["unit_value"])
    return item


def _release(asset: Asset, disposal: Disposal, *, user, reason: str, to_location=None) -> None:
    """A reserved asset available again — where it is, or `to_location` (RN-02 applies)."""
    asset.refresh_from_db()
    place = to_location or asset.current_location
    if not area_accepts(place.area_type, AssetStatus.AVAILABLE):
        raise DomainError(
            _("%(asset)s is at %(location)s: move it back to a stock area first.")
            % {"asset": asset.horizon_id, "location": place.code},
            field="item",
        )
    services.change_status(
        asset,
        to_status=AssetStatus.AVAILABLE,
        user=user,
        document_ref=disposal.ref,
        reason=reason,
        to_location=to_location,
    )


@transaction.atomic
def remove_item(item: DisposalItem, *, user) -> None:
    """Take an item out before it is picked: a reserved asset is available again."""
    disposal = _lock_open(item.disposal)
    item = DisposalItem.objects.select_for_update().get(pk=item.pk)
    if item.picked_quantity:
        raise DomainError(
            _("This item was already picked: cancel the disposal to give it back."),
            field="item",
        )
    if item.asset_id and item.asset.status == AssetStatus.RESERVED:
        _release(
            item.asset,
            disposal,
            user=user,
            reason=_("Removed from %(code)s") % {"code": disposal.code},
        )
    item.delete()


# --- Picking -----------------------------------------------------------------------------------


def _check_shipping_place(disposal: Disposal, location: Location) -> None:
    if location.area_type != AreaType.SHIPPING or location.warehouse_id != disposal.warehouse_id:
        raise DomainError(
            _("Read a shipping area of warehouse %(code)s.") % {"code": disposal.warehouse.code},
            field="shipping_location",
        )
    if not location.is_active:
        raise DomainError(_("This location is inactive."), field="shipping_location")


def _start_picking(disposal: Disposal) -> None:
    if disposal.status == DisposalStatus.RESERVED:
        disposal.status = DisposalStatus.PICKING
        disposal.save(update_fields=["status", "updated_at"])
    appointment = disposal.appointment
    if appointment is not None and appointment.status in (
        AppointmentStatus.SCHEDULED,
        AppointmentStatus.CONFIRMED,
    ):
        Appointment.objects.filter(pk=appointment.pk).update(
            status=AppointmentStatus.IN_PROGRESS, updated_at=timezone.now()
        )


@transaction.atomic
def pick_asset(disposal: Disposal, asset: Asset, *, shipping_location: Location, user):
    """An ID read at picking: it must be on the list (RN: divergence never picked) and goes to
    the shipping area."""
    disposal = _lock_open(disposal)
    _check_shipping_place(disposal, shipping_location)
    item = DisposalItem.objects.select_for_update().filter(disposal=disposal, asset=asset).first()
    if item is None:
        raise DomainError(
            _("%(asset)s is not in this disposal.") % {"asset": asset.horizon_id},
            field="code",
        )
    if item.picked_quantity:
        raise DomainError(
            _("%(asset)s was already picked.") % {"asset": asset.horizon_id}, field="code"
        )
    asset.refresh_from_db()
    if asset.current_location_id != shipping_location.pk or asset.current_container_id:
        services.move_asset(
            asset,
            user=user,
            to_location=shipping_location,
            kind=EventKind.PICKING,
            document_ref=disposal.ref,
            reason=disposal.code,
        )
    item.picked_quantity = 1
    item.picked_at = timezone.now()
    item.picked_by = user
    item.save(update_fields=["picked_quantity", "picked_at", "picked_by"])
    _start_picking(disposal)
    return item


@transaction.atomic
def pick_accessory(
    disposal: Disposal,
    item: DisposalItem,
    quantity: int,
    *,
    user,
    container: Container | None = None,
    location: Location | None = None,
) -> DisposalItem:
    """Units of an accessory line taken from a container or a location (its balance goes
    down; they wait for the shipping with the disposal)."""
    disposal = _lock_open(disposal)
    item = DisposalItem.objects.select_for_update().get(pk=item.pk, disposal=disposal)
    if item.accessory_model_id is None:
        raise DomainError(_("Read the asset's ID."), field="item")
    if quantity < 1 or item.picked_quantity + quantity > item.quantity:
        raise DomainError(
            _("Only %(left)d left to pick.") % {"left": item.quantity - item.picked_quantity},
            field="quantity",
        )
    place = container.current_location if container is not None else location
    if place is None or place.warehouse_id != disposal.warehouse_id:
        raise DomainError(
            _("Read a container or location of warehouse %(code)s.")
            % {"code": disposal.warehouse.code},
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
        document_ref=disposal.ref,
        reason=disposal.code,
    )
    item.picked_quantity += quantity
    item.picked_at = timezone.now()
    item.picked_by = user
    item.save(update_fields=["picked_quantity", "picked_at", "picked_by"])
    _start_picking(disposal)
    return item


# --- Files -------------------------------------------------------------------------------------


def add_file(disposal: Disposal, *, kind: str, upload, user) -> DisposalFile:
    if disposal.status == DisposalStatus.CANCELLED:
        raise DomainError(_("This disposal was cancelled."), field="disposal")
    if kind not in DisposalFileKind.values:
        raise DomainError(_("Choose the kind of file."), field="kind")
    if kind == DisposalFileKind.CERTIFICATE and disposal.kind != DisposalKind.DISCARD:
        raise DomainError(_("Only discards have a destination certificate."), field="kind")
    name = clean_filename(upload.name or "")
    errors = check_document(
        name, upload.size, settings.PRICE_DOCUMENT_MAX_MB * 1024 * 1024, attachment_messages()
    )
    if errors:
        raise DomainError(" ".join(str(e) for e in errors), field="file")
    item = DisposalFile(
        disposal=disposal,
        kind=kind,
        name=name,
        size=upload.size,
        content_type=content_type_for(name),
        uploaded_by=user,
    )
    item.file.save(name, upload, save=False)
    item.save()
    return item


def remove_file(item: DisposalFile) -> None:
    status = Disposal.objects.values_list("status", flat=True).get(pk=item.disposal_id)
    if status == DisposalStatus.SHIPPED and item.kind != DisposalFileKind.OTHER:
        raise DomainError(_("The documents of a shipped disposal are kept."), field="file")
    item.delete()


# --- Shipping and cancelling -------------------------------------------------------------------


def problems(disposal: Disposal) -> list[str]:
    """What still keeps the disposal from shipping (shown on its page)."""
    found = []
    items = list(disposal.items.select_related("asset__current_location", "accessory_model"))
    if not items:
        found.append(_("Add the assets or accessories that leave."))
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
        if asset.held_for_dispute:
            found.append(_("%(asset)s is held for a dispute.") % {"asset": asset.horizon_id})
        if asset.current_location.area_type != AreaType.SHIPPING:
            found.append(
                _("%(asset)s left the shipping area: pick it again.") % {"asset": asset.horizon_id}
            )
    if not disposal.document_number.strip():
        found.append(_("Enter the shipping document's number."))
    kinds = set(disposal.files.values_list("kind", flat=True))
    if DisposalFileKind.DOCUMENT not in kinds:
        found.append(_("Attach the shipping document."))
    if disposal.kind == DisposalKind.DISCARD and DisposalFileKind.CERTIFICATE not in kinds:
        found.append(_("Attach the destination certificate (required to write off a discard)."))
    return found


@transaction.atomic
def ship(disposal: Disposal, *, user) -> Disposal:
    """Everything picked, the document attached (a discard: also its certificate — RN-23): the
    assets are written off (SHIPPING events), the accessories leave, the appointment is done."""
    disposal = _lock_open(disposal)
    found = problems(disposal)
    if found:
        raise DomainError(" ".join(str(p) for p in found), field="disposal")
    for item in disposal.items.select_related("asset", "accessory_model"):
        if item.asset_id:
            services.change_status(
                item.asset,
                to_status=AssetStatus.WRITTEN_OFF,
                user=user,
                kind=EventKind.SHIPPING,
                document_ref=disposal.ref,
                reason=disposal.code,
            )
        else:
            MovementEvent.objects.create(
                kind=EventKind.SHIPPING,
                user=user,
                accessory_model=item.accessory_model,
                quantity=item.quantity,
                accessory_condition=item.condition,
                document_ref=disposal.ref,
                reason=disposal.code,
            )
    disposal.status = DisposalStatus.SHIPPED
    disposal.shipped_by = user
    disposal.shipped_at = timezone.now()
    disposal.save()
    if disposal.appointment_id and disposal.appointment.status not in (
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ):
        Appointment.objects.filter(pk=disposal.appointment_id).update(
            status=AppointmentStatus.DONE, updated_at=timezone.now()
        )
    return disposal


@transaction.atomic
def cancel(disposal: Disposal, *, user, reason: str) -> Disposal:
    """Everything goes back: assets picked return to where they were picked from, reserved ones
    are available again (scrap ones stay scrap), accessories picked return to their balance."""
    if not reason.strip():
        raise DomainError(_("Say why the disposal is cancelled."), field="reason")
    disposal = _lock_open(disposal)
    back = _("Cancelled: %(code)s") % {"code": disposal.code}
    for item in disposal.items.select_related("asset", "accessory_model"):
        asset = item.asset
        if asset is None:
            continue
        picking = (
            asset.events.filter(kind=EventKind.PICKING, document_ref=disposal.ref)
            .select_related("from_location", "from_container")
            .order_by("-at", "-id")
            .first()
        )
        if asset.status == AssetStatus.RESERVED:
            _release(
                asset,
                disposal,
                user=user,
                reason=back,
                to_location=picking.from_location if picking else None,
            )
        elif picking is not None:
            services.move_asset(
                asset,
                user=user,
                to_location=picking.from_location,
                document_ref=disposal.ref,
                reason=back,
            )
    for event in MovementEvent.objects.filter(
        kind=EventKind.PICKING, document_ref=disposal.ref, accessory_model__isnull=False
    ).select_related("from_container", "from_location", "accessory_model"):
        services.add_accessories(
            event.accessory_model,
            event.quantity,
            user=user,
            container=event.from_container,
            location=None if event.from_container_id else event.from_location,
            condition=event.accessory_condition or AccessoryCondition.GOOD,
            kind=EventKind.REVERSAL,
            document_ref=disposal.ref,
            reason=back,
        )
    disposal.status = DisposalStatus.CANCELLED
    disposal.cancelled_by = user
    disposal.cancelled_at = timezone.now()
    disposal.cancel_reason = reason.strip()
    disposal.save()
    return disposal


def record_parts(asset: Asset, *, user) -> Disposal:
    """Taking a scrap asset apart is its way out as parts: recorded as a shipped disposal."""
    disposal = create_with_code(
        Disposal,
        kind=DisposalKind.PARTS,
        status=DisposalStatus.SHIPPED,
        warehouse=asset.current_location.warehouse,
        created_by=user,
        shipped_by=user,
        shipped_at=timezone.now(),
    )
    DisposalItem.objects.create(
        disposal=disposal, asset=asset, picked_quantity=1, picked_at=timezone.now(), picked_by=user
    )
    return disposal


def totals(disposal: Disposal) -> dict:
    """Units, assets, accessories and the total value (Σ quantity × unit value)."""
    assets = accessories = 0
    total = Decimal("0.00")
    valued = False
    for item in disposal.items.all():
        if item.asset_id:
            assets += 1
        else:
            accessories += item.quantity
        if item.unit_value is not None:
            valued = True
            total += item.unit_value * item.quantity
    return {
        "assets": assets,
        "accessories": accessories,
        "total_value": f"{total:.2f}" if valued else None,
    }
