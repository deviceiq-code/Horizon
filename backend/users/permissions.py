from rest_framework.permissions import BasePermission

from .models import ADMINISTRATOR


def is_administrator(user) -> bool:
    """Active users with the Administrator role (or Django superusers) can do everything."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return user.is_superuser or user.roles.filter(key=ADMINISTRATOR).exists()


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return is_administrator(request.user)
