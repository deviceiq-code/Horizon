"""Roles of the system's users. A user can have several roles; the "Administrator" role is a
system role (cannot be changed or deleted) that gives access to everything."""

import posixpath
import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from config.photos import PhotoMixin, photo_version, remove_file_later

ADMINISTRATOR = "administrator"


class Role(models.Model):
    # Stable identifier of system roles (e.g. "administrator"); empty for roles created in the app
    key = models.SlugField(_("key"), max_length=50, blank=True)
    name = models.CharField(_("name"), max_length=80)
    description = models.TextField(_("description"), blank=True)
    # Created by the system: cannot be changed or deleted
    is_system = models.BooleanField(_("system role"), default=False)
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="roles", verbose_name=_("users")
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="role_unique_name"),
            models.UniqueConstraint(
                fields=["key"], condition=~models.Q(key=""), name="role_unique_key"
            ),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def administrator(cls) -> "Role":
        """The Administrator system role (created by a migration; recreated if missing)."""
        role, _created = cls.objects.get_or_create(
            key=ADMINISTRATOR,
            defaults={
                "name": "Administrator",
                "description": "Full access to the system.",
                "is_system": True,
            },
        )
        return role


def _photo_path(instance: "UserProfile", filename: str) -> str:
    # Random name: a new photo gets a new address (the browser does not show the old one)
    return f"users/{uuid.uuid4().hex}{posixpath.splitext(filename)[1].lower()}"


class UserProfile(PhotoMixin, models.Model):
    """What the app keeps about a user besides Django's user: their photo (square, shown in a
    circle). Created when first needed (UserProfile.for_user)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("user"),
    )
    photo = models.FileField(_("photo"), upload_to=_photo_path, max_length=255, blank=True)

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")

    def __str__(self):
        return str(self.user)

    @classmethod
    def for_user(cls, user) -> "UserProfile":
        profile, _created = cls.objects.get_or_create(user=user)
        return profile


@receiver(post_delete, sender=UserProfile)
def _remove_photo_file(sender, instance, **kwargs):
    # Also when the user is deleted (the profile goes with it)
    remove_file_later(instance.photo.storage, instance.photo.name)


def user_photo_version(user) -> str | None:
    """The user's photo version (see config.photos.photo_version), None without a photo."""
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None
    return photo_version(profile.photo)
