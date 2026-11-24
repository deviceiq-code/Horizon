"""Who may do what in the inventory, by the users' system roles (users.models.SYSTEM_ROLES).
Administrators may do everything. Checked in the API (and in services where the rule is about
segregation of duties, in later phases)."""

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS, BasePermission

from users.models import (
    COMMERCIAL_FINANCE,
    INSPECTION_TECHNICIAN,
    INVENTORY_SUPERVISOR,
    RECEIVER,
    REMARKETING_ANALYST,
    STOREKEEPER,
)
from users.permissions import is_administrator

# Moving assets and containers (scan the object, scan the destination)
MOVERS = (RECEIVER, STOREKEEPER, INVENTORY_SUPERVISOR)
# Creating containers and reserving label ranges
LABELERS = (RECEIVER, STOREKEEPER, INVENTORY_SUPERVISOR)
# Keeping the warehouses' locations
LOCATION_KEEPERS = (INVENTORY_SUPERVISOR,)
# Scheduling receivings and shipments, preparing expected lists
SCHEDULERS = (REMARKETING_ANALYST, INVENTORY_SUPERVISOR)
# Who may see expected lists — never the receivers who count (blind count, RN-17)
EXPECTED_READERS = (REMARKETING_ANALYST, INVENTORY_SUPERVISOR, COMMERCIAL_FINANCE)
# Opening lots, triage, occurrences, closing
RECEIVERS = (RECEIVER, INVENTORY_SUPERVISOR)
# Inspecting: reports, photos, findings, erasure certificates, part harvesting
INSPECTORS = (INSPECTION_TECHNICIAN, INVENTORY_SUPERVISOR)
# Inventory catalogs (grade meanings, penalty table, erasure tools) and approvals
SUPERVISORS = (INVENTORY_SUPERVISOR,)
# Marking reports as sent to customers
SENDERS = (COMMERCIAL_FINANCE, INVENTORY_SUPERVISOR)
# Disposals: creating, reserving assets, values, cancelling
DISPOSERS = (COMMERCIAL_FINANCE, REMARKETING_ANALYST, INVENTORY_SUPERVISOR)
# Disposals: picking (reading each ID) and shipping
PICKERS = (STOREKEEPER, INVENTORY_SUPERVISOR)
# Transfers: requesting (supervisors approve)
TRANSFER_REQUESTERS = (REMARKETING_ANALYST, INVENTORY_SUPERVISOR)
# Transfers: picking and sending at the origin, receiving at the destination
TRANSFER_HANDLERS = (STOREKEEPER, RECEIVER, INVENTORY_SUPERVISOR)


def has_role(user, *keys: str) -> bool:
    if is_administrator(user):
        return True
    if not user or not user.is_authenticated:
        return False
    return user.roles.filter(key__in=keys).exists()


def role_permission(*keys: str, read_for_all: bool = True):
    """A DRF permission: reading for everyone signed in (unless read_for_all=False), writing
    for administrators and users with one of these roles."""

    class RolePermission(BasePermission):
        message = _("You do not have permission to perform this action.")

        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            if read_for_all and request.method in SAFE_METHODS:
                return True
            return has_role(request.user, *keys)

    return RolePermission
