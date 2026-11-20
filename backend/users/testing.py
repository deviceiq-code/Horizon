"""Helpers for tests of any app."""

from django.contrib.auth import get_user_model

from .models import Role


def make_account_manager(first_name: str, last_name: str, email: str, verticals=()):
    """A user with the "Account Manager" role (and the verticals they work in)."""
    user = get_user_model().objects.create_user(
        email.split("@")[0],
        email=email,
        first_name=first_name,
        last_name=last_name,
        password="Account-manager-2026",
    )
    Role.account_manager().users.add(user)
    if verticals:
        user.profile.verticals.add(*verticals)
    return user
