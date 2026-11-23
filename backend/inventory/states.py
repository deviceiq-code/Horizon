"""The asset's life in the warehouse: its statuses, the transitions allowed between them (RN-01)
and which statuses each kind of area accepts (RN-02). Pure, tested; the only place these rules
live. The movement service (inventory/services.py) applies them."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class DomainError(Exception):
    """A business rule refused the operation. `message` is translated, for the user."""

    def __init__(self, message, field: str | None = None):
        super().__init__(str(message))
        self.message = message
        self.field = field


class AssetStatus(models.TextChoices):
    IN_TRIAGE = "in_triage", _("In Triage")
    AWAITING_INSPECTION = "awaiting_inspection", _("Awaiting Inspection")
    IN_INSPECTION = "in_inspection", _("In Inspection")
    BLOCKED = "blocked", _("Blocked")
    AVAILABLE = "available", _("Available")
    RESERVED = "reserved", _("Reserved")
    SCRAP = "scrap", _("Scrap")
    IN_TRANSIT = "in_transit", _("In Transit")
    WRITTEN_OFF = "written_off", _("Written Off")


class AreaType(models.TextChoices):
    DOCK = "dock", _("Dock")
    INSPECTION_QUEUE = "inspection_queue", _("Inspection Queue")
    BENCH = "bench", _("Bench")
    QUARANTINE = "quarantine", _("Quarantine")
    STOCK = "stock", _("Stock")
    SCRAP = "scrap", _("Scrap")
    SHIPPING = "shipping", _("Shipping")
    VIRTUAL_TRANSIT = "virtual_transit", _("In Transit (Virtual)")


S = AssetStatus

FINAL_STATUSES = {S.WRITTEN_OFF}

# Allowed transitions (before → afters). Going in transit and back is handled apart: any status
# that is not final may go IN_TRANSIT, and an asset leaves IN_TRANSIT only to the status it had
# before (kept by the transfer).
TRANSITIONS: dict[str, set[str]] = {
    S.IN_TRIAGE: {S.AWAITING_INSPECTION},
    S.AWAITING_INSPECTION: {S.IN_INSPECTION},
    S.IN_INSPECTION: {S.AVAILABLE, S.BLOCKED, S.SCRAP},
    # Release confirmed → finish the inspection; block expired → supervisor's decision
    S.BLOCKED: {S.IN_INSPECTION, S.SCRAP, S.AVAILABLE},
    # A problem found later (e.g. quarantine) blocks an available asset
    S.AVAILABLE: {S.RESERVED, S.SCRAP, S.BLOCKED},
    S.RESERVED: {S.AVAILABLE, S.WRITTEN_OFF},
    S.SCRAP: {S.WRITTEN_OFF},
    S.IN_TRANSIT: set(),
    S.WRITTEN_OFF: set(),
}


def can_transition(before: str, after: str, *, status_before_transit: str | None = None) -> bool:
    if before == after:
        return False
    if after == S.IN_TRANSIT:
        return before not in FINAL_STATUSES and before != S.IN_TRANSIT
    if before == S.IN_TRANSIT:
        return status_before_transit is not None and after == status_before_transit
    return after in TRANSITIONS.get(before, set())


def check_transition(before: str, after: str, *, status_before_transit: str | None = None):
    """RN-01: raise DomainError when the table does not allow it."""
    if not can_transition(before, after, status_before_transit=status_before_transit):
        raise DomainError(
            _("An asset cannot go from %(before)s to %(after)s.")
            % {"before": S(before).label, "after": S(after).label},
            field="status",
        )


# Which statuses each kind of area accepts (RN-02). Quarantine also takes any asset held for a
# dispute.
AREA_STATUSES: dict[str, set[str]] = {
    AreaType.DOCK: {S.IN_TRIAGE},
    AreaType.INSPECTION_QUEUE: {S.AWAITING_INSPECTION},
    AreaType.BENCH: {S.IN_INSPECTION},
    AreaType.QUARANTINE: {S.BLOCKED},
    AreaType.STOCK: {S.AVAILABLE, S.RESERVED},
    AreaType.SCRAP: {S.SCRAP},
    AreaType.SHIPPING: {S.RESERVED, S.SCRAP},
    AreaType.VIRTUAL_TRANSIT: {S.IN_TRANSIT},
}


def area_accepts(area_type: str, status: str, *, held_for_dispute: bool = False) -> bool:
    if area_type == AreaType.QUARANTINE and held_for_dispute:
        return True
    return status in AREA_STATUSES.get(area_type, set())


def check_area(area_type: str, status: str, *, held_for_dispute: bool = False):
    """RN-02: raise DomainError when the area does not take assets in this status."""
    if not area_accepts(area_type, status, held_for_dispute=held_for_dispute):
        raise DomainError(
            _("A %(area)s area does not take assets that are %(status)s.")
            % {"area": AreaType(area_type).label, "status": S(status).label},
            field="destination",
        )


def accepted_statuses(area_type: str) -> list[str]:
    """For display: the statuses an area takes, in the statuses' order."""
    allowed = AREA_STATUSES.get(area_type, set())
    return [status for status in S.values if status in allowed]
