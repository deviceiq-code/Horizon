"""Who may do what in the inventory, by the users' system roles (users.models.SYSTEM_ROLES).
Administrators may do everything. Checked in the API (and in services where the rule is about
segregation of duties, in later phases)."""

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS, BasePermission

from users.models import INVENTORY_SUPERVISOR, RECEIVER, STOREKEEPER
from users.permissions import is_administrator

# Moving assets and containers (scan the object, scan the destination)
MOVERS = (RECEIVER, STOREKEEPER, INVENTORY_SUPERVISOR)
# Creating containers and reserving label ranges
LABELERS = (RECEIVER, STOREKEEPER, INVENTORY_SUPERVISOR)
# Keeping the warehouses' locations
LOCATION_KEEPERS = (INVENTORY_SUPERVISOR,)


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


class IsAdministratorToWrite(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or is_administrator(request.user)
