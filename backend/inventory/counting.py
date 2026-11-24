"""Inventory counts (Phase 7) and the location divergence while moving (RN-19). The only code
that changes a count; asset statuses and places still change only through inventory.services.

open (cyclic: some locations and everything under them; general: the whole warehouse) → the
locations freeze (services.check_not_counting) → blind readings: asset IDs and accessory
quantities per location → close: the divergences (`find_divergences`, pure) → each is an
adjustment a supervisor who did not count approves or rejects (RN-26) → finished.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from catalogs.models import Tracking
from users.models import INVENTORY_SUPERVISOR

from . import services
from .models import (
    AccessoryBalance,
    AccessoryCondition,
    AdjustmentStatus,
    Asset,
    Container,
    CountDivergence,
    CountKind,
    CountReading,
    CountStatus,
    DivergenceKind,
    EventKind,
    InventoryCount,
    Location,
    Occurrence,
    OccurrenceKind,
)
from .receiving import create_with_code
from .states import AssetStatus, DomainError

# --- Divergences (pure) --------------------------------------------------------------------------


@dataclass(frozen=True)
class Found:
    """A divergence found (before it is stored)."""

    kind: str
    asset: int | None = None
    expected_location: int | None = None
    found_location: int | None = None
    accessory: tuple | None = None  # (model id, condition, container id | None, location id)
    expected_quantity: int | None = None
    counted_quantity: int | None = None


@dataclass
class Comparison:
    divergences: list[Found] = field(default_factory=list)
    expected: int = 0
    matched: int = 0


def find_divergences(
    *,
    scope: set[int],
    expected_assets: dict[int, int],
    read_assets: dict[int, int],
    expected_balances: dict[tuple, int],
    counted_balances: dict[tuple, int],
) -> Comparison:
    """`expected_assets` / `read_assets`: asset id → location id (records / readings);
    balances: (model, condition, container, location) → quantity. An expected asset not read
    is not found; read elsewhere in the scope, at another location; read but recorded outside
    the scope (or not in stock), not expected here. Balances differ when the quantities do."""
    result = Comparison(expected=len(expected_assets))
    for asset, location in sorted(expected_assets.items()):
        read = read_assets.get(asset)
        if read is None:
            result.divergences.append(
                Found(DivergenceKind.NOT_FOUND, asset=asset, expected_location=location)
            )
        elif read != location:
            result.divergences.append(
                Found(
                    DivergenceKind.OTHER_LOCATION,
                    asset=asset,
                    expected_location=location,
                    found_location=read,
                )
            )
        else:
            result.matched += 1
    for asset, read in sorted(read_assets.items()):
        if asset not in expected_assets:
            result.divergences.append(
                Found(DivergenceKind.UNEXPECTED, asset=asset, found_location=read)
            )
    for key in sorted(set(expected_balances) | set(counted_balances), key=str):
        expected = expected_balances.get(key, 0)
        counted = counted_balances.get(key, 0)
        if expected != counted and key[3] in scope:
            result.divergences.append(
                Found(
                    DivergenceKind.BALANCE,
                    accessory=key,
                    expected_quantity=expected,
                    counted_quantity=counted,
                )
            )
    return result


# --- Opening -----------------------------------------------------------------------------------


def _descendants(locations) -> set[int]:
    ids = {loc.pk for loc in locations}
    frontier = set(ids)
    while frontier:
        frontier = (
            set(Location.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)) - ids
        )
        ids |= frontier
    return ids


@transaction.atomic
def open_count(
    *, warehouse, kind: str, user, responsible=None, locations=(), notes: str = ""
) -> InventoryCount:
    if kind not in CountKind.values:
        raise DomainError(_("Choose the kind of count."), field="kind")
    if kind == CountKind.GENERAL:
        scope = set(
            Location.objects.filter(warehouse=warehouse, is_active=True).values_list(
                "pk", flat=True
            )
        )
    else:
        locations = list(locations)
        if not locations:
            raise DomainError(_("Choose the locations to count."), field="locations")
        if any(loc.warehouse_id != warehouse.pk for loc in locations):
            raise DomainError(
                _("Choose locations of warehouse %(code)s.") % {"code": warehouse.code},
                field="locations",
            )
        scope = _descendants(locations)
    if not scope:
        raise DomainError(_("This warehouse has no locations to count."), field="locations")
    busy = (
        InventoryCount.objects.filter(status=CountStatus.COUNTING, locations__in=scope)
        .distinct()
        .first()
    )
    if busy is not None:
        raise DomainError(
            _("Some of these locations are already being counted (%(code)s).")
            % {"code": busy.code},
            field="locations",
        )
    count = create_with_code(
        InventoryCount,
        warehouse=warehouse,
        kind=kind,
        responsible=responsible or user,
        notes=notes,
        created_by=user,
    )
    count.locations.set(scope)
    return count


def _lock(count: InventoryCount, *statuses) -> InventoryCount:
    count = InventoryCount.objects.select_for_update().get(pk=count.pk)
    if count.status not in statuses:
        raise DomainError(
            _("Not possible while the count is %(status)s.")
            % {"status": CountStatus(count.status).label},
            field="count",
        )
    return count


def _in_scope(count: InventoryCount, location: Location) -> None:
    if not count.locations.filter(pk=location.pk).exists():
        raise DomainError(
            _("%(code)s is not one of the locations of this count.") % {"code": location.code},
            field="location",
        )


# --- Readings (blind) --------------------------------------------------------------------------


@transaction.atomic
def read_asset(count: InventoryCount, asset: Asset, *, location: Location, user) -> CountReading:
    """An asset's ID read at a location (read again at another one: the last reading counts)."""
    count = _lock(count, CountStatus.COUNTING)
    _in_scope(count, location)
    reading, _created = CountReading.objects.update_or_create(
        count=count,
        asset=asset,
        defaults={"location": location, "counted_by": user, "counted_at": timezone.now()},
    )
    return reading


@transaction.atomic
def read_accessories(
    count: InventoryCount,
    asset_model,
    quantity: int,
    *,
    location: Location,
    user,
    container: Container | None = None,
    condition: str = AccessoryCondition.GOOD,
) -> CountReading:
    """A quantity of an accessory model counted at a location (or in a container there); the
    readings of the same model and place add up."""
    count = _lock(count, CountStatus.COUNTING)
    _in_scope(count, location)
    if asset_model.tracking != Tracking.QUANTITY:
        raise DomainError(
            _("Only models controlled by quantity are counted by quantity."), field="asset_model"
        )
    if quantity < 0:
        raise DomainError(_("Enter a quantity of 0 or more."), field="quantity")
    if container is not None and container.current_location_id != location.pk:
        raise DomainError(
            _("Container %(code)s is not at this location.") % {"code": container.code},
            field="container",
        )
    if condition not in AccessoryCondition.values:
        raise DomainError(_("Choose the condition."), field="condition")
    return CountReading.objects.create(
        count=count,
        location=location,
        accessory_model=asset_model,
        container=container,
        quantity=quantity,
        condition=condition,
        counted_by=user,
    )


@transaction.atomic
def remove_reading(reading: CountReading) -> None:
    _lock(reading.count, CountStatus.COUNTING)
    reading.delete()


# --- Closing -----------------------------------------------------------------------------------

IN_STOCK_EXCLUDED = (AssetStatus.WRITTEN_OFF, AssetStatus.IN_TRANSIT)


@transaction.atomic
def close(count: InventoryCount, *, user) -> InventoryCount:
    """Compare the readings with the records and store the divergences (adjustments pending)."""
    count = _lock(count, CountStatus.COUNTING)
    scope = set(count.locations.values_list("pk", flat=True))
    expected_assets = dict(
        Asset.objects.filter(current_location_id__in=scope)
        .exclude(status__in=IN_STOCK_EXCLUDED)
        .values_list("pk", "current_location_id")
    )
    read_assets = dict(
        count.readings.filter(asset__isnull=False).values_list("asset_id", "location_id")
    )
    expected_balances: dict[tuple, int] = {}
    for balance in AccessoryBalance.objects.filter(quantity__gt=0).select_related("container"):
        place = (
            balance.container.current_location_id if balance.container_id else balance.location_id
        )
        if place in scope:
            key = (balance.asset_model_id, balance.condition, balance.container_id, place)
            expected_balances[key] = expected_balances.get(key, 0) + balance.quantity
    counted_balances: dict[tuple, int] = {}
    for reading in count.readings.filter(accessory_model__isnull=False):
        key = (
            reading.accessory_model_id,
            reading.condition,
            reading.container_id,
            reading.location_id,
        )
        counted_balances[key] = counted_balances.get(key, 0) + reading.quantity
    result = find_divergences(
        scope=scope,
        expected_assets=expected_assets,
        read_assets=read_assets,
        expected_balances=expected_balances,
        counted_balances=counted_balances,
    )
    for found in result.divergences:
        extra = {}
        if found.accessory:
            model, condition, container, location = found.accessory
            extra = {
                "accessory_model_id": model,
                "condition": condition,
                "container_id": container,
                "found_location_id": location,
            }
        CountDivergence.objects.create(
            count=count,
            kind=found.kind,
            asset_id=found.asset,
            expected_location_id=found.expected_location,
            found_location_id=extra.pop("found_location_id", found.found_location),
            expected_quantity=found.expected_quantity,
            counted_quantity=found.counted_quantity,
            **extra,
        )
    count.expected_assets = result.expected
    count.matched_assets = result.matched
    count.status = CountStatus.CLOSED if result.divergences else CountStatus.FINISHED
    count.closed_by = user
    count.closed_at = timezone.now()
    if not result.divergences:
        count.finished_at = count.closed_at
    count.save()
    return count


@transaction.atomic
def cancel(count: InventoryCount, *, user, reason: str) -> InventoryCount:
    if not reason.strip():
        raise DomainError(_("Say why the count is cancelled."), field="reason")
    count = _lock(count, CountStatus.COUNTING)
    count.status = CountStatus.CANCELLED
    count.cancelled_by = user
    count.cancelled_at = timezone.now()
    count.cancel_reason = reason.strip()
    count.save()
    return count


# --- Adjustments (RN-26) -----------------------------------------------------------------------


def counters(count: InventoryCount) -> set[int]:
    """Who counted (made readings) — plus the one responsible for the count."""
    ids = set(count.readings.values_list("counted_by_id", flat=True))
    ids.add(count.responsible_id)
    return ids


def _check_free(asset: Asset) -> None:
    from .disposals import open_disposal_of
    from .transfers import open_transfer_of

    busy = open_disposal_of(asset) or open_transfer_of(asset)
    if busy is not None:
        raise DomainError(
            _("%(asset)s is in %(code)s: finish or cancel it first.")
            % {"asset": asset.horizon_id, "code": busy.code},
            field="divergence",
        )


def _lost_before(asset: Asset) -> str | None:
    """The status an asset had before an earlier count wrote it off as lost, if that was it."""
    last = asset.events.exclude(kind=EventKind.LABEL_REPRINT).order_by("-at", "-id").first()
    if (
        last is not None
        and last.kind == EventKind.INVENTORY_ADJUSTMENT
        and last.status_after == AssetStatus.WRITTEN_OFF
    ):
        return last.status_before
    return None


@transaction.atomic
def decide(divergence: CountDivergence, *, user, approve: bool, reason: str) -> CountDivergence:
    """A supervisor who did not count approves (the adjustment is applied) or rejects it
    (nothing changes); a reason is always required. The count finishes with the last one."""
    divergence = (
        CountDivergence.objects.select_for_update().select_related("count").get(pk=divergence.pk)
    )
    count = _lock(divergence.count, CountStatus.CLOSED)
    if divergence.status != AdjustmentStatus.PENDING:
        raise DomainError(_("This adjustment was already decided."), field="divergence")
    if user.pk in counters(count):
        raise DomainError(
            _("Adjustments are approved by a supervisor who did not count (RN-26)."),
            field="divergence",
        )
    if not reason.strip():
        raise DomainError(_("Give the reason for the decision."), field="reason")
    if approve:
        _apply(divergence, user=user, reason=reason.strip())
    divergence.status = AdjustmentStatus.APPROVED if approve else AdjustmentStatus.REJECTED
    divergence.reason = reason.strip()
    divergence.decided_by = user
    divergence.decided_at = timezone.now()
    divergence.save()
    if not count.divergences.filter(status=AdjustmentStatus.PENDING).exists():
        count.status = CountStatus.FINISHED
        count.finished_at = timezone.now()
        count.save(update_fields=["status", "finished_at"])
    return divergence


def _apply(divergence: CountDivergence, *, user, reason: str) -> None:
    count = divergence.count
    ref = count.ref
    text = f"{count.code}: {reason}"
    if divergence.kind == DivergenceKind.BALANCE:
        services.adjust_balance(
            divergence.accessory_model,
            counted=divergence.counted_quantity or 0,
            user=user,
            document_ref=ref,
            reason=text,
            condition=divergence.condition,
            container=divergence.container,
            location=divergence.found_location,
        )
        return
    asset = Asset.objects.get(pk=divergence.asset_id)
    if divergence.kind == DivergenceKind.NOT_FOUND:
        _check_free(asset)
        if asset.status in IN_STOCK_EXCLUDED:
            raise DomainError(
                _("%(asset)s is no longer in stock: reject this adjustment.")
                % {"asset": asset.horizon_id},
                field="divergence",
            )
        services.adjust_lost(asset, user=user, document_ref=ref, reason=text)
        Occurrence.objects.create(
            count=count,
            kind=OccurrenceKind.LOST,
            asset=asset,
            asset_model=asset.asset_model,
            expected_serial=asset.serial,
            description=text,
            created_by=user,
        )
        return
    # Found at another location, or not expected here: the records follow the count
    status = None
    if asset.status in IN_STOCK_EXCLUDED:
        status = _lost_before(asset)
        if status is None:
            raise DomainError(
                _(
                    "%(asset)s left the stock (or is in transit): it cannot be brought back "
                    "by a count — reject this adjustment and register an occurrence."
                )
                % {"asset": asset.horizon_id},
                field="divergence",
            )
    else:
        _check_free(asset)
    services.adjust_place(
        asset,
        location=divergence.found_location,
        user=user,
        document_ref=ref,
        reason=text,
        status=status,
    )


# --- RN-19: location divergence while moving ---------------------------------------------------


def report_location_mismatch(target, origin: Location, *, user) -> Occurrence | None:
    """The object was read at `origin`, but the records say it is elsewhere: an occurrence and
    an alert for the supervisors (the movement goes on)."""
    from .followups import alert

    recorded = target.current_location
    if recorded is None or recorded.pk == origin.pk:
        return None
    with transaction.atomic():
        code = target.horizon_id if isinstance(target, Asset) else target.code
        occurrence = Occurrence.objects.create(
            kind=OccurrenceKind.LOCATION_MISMATCH,
            asset=target if isinstance(target, Asset) else None,
            asset_model=target.asset_model if isinstance(target, Asset) else None,
            description=_("%(code)s was read at %(read)s; the records said %(recorded)s.")
            % {"code": code, "read": origin.code, "recorded": recorded.code},
            created_by=user,
        )
        alert(
            f"location_mismatch:{occurrence.pk}",
            "location_mismatch",
            ref=f"occurrence:{occurrence.pk}",
            role_key=INVENTORY_SUPERVISOR,
            code=code,
            read=origin.code,
            recorded=recorded.code,
        )
    return occurrence
