"""Users' roles and profiles. A user can have several roles; "Administrator" (access to
everything) and "Account Manager" (can be a customer's account manager) are system roles
(cannot be changed or deleted). The profile holds the employee data, the photo and, for
account managers, the business verticals they work in (set by administrators)."""

import posixpath
import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from config.keywords import keywords_field
from config.photos import PhotoMixin, photo_version, remove_file_later

ADMINISTRATOR = "administrator"
ACCOUNT_MANAGER = "account_manager"

SYSTEM_ROLES = {
    ADMINISTRATOR: ("Administrator", "Full access to the system."),
    ACCOUNT_MANAGER: ("Account Manager", "Can be the account manager of customers."),
}


class Role(models.Model):
    # Stable identifier of system roles (e.g. "administrator"); empty for roles created in the app
    key = models.SlugField(_("key"), max_length=50, blank=True)
    name = models.CharField(_("name"), max_length=80)
    description = models.TextField(_("description"), blank=True)
    keywords = keywords_field()
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
    def system(cls, key: str) -> "Role":
        """A system role (created by a migration; recreated if missing)."""
        name, description = SYSTEM_ROLES[key]
        role, _created = cls.objects.get_or_create(
            key=key, defaults={"name": name, "description": description, "is_system": True}
        )
        return role

    @classmethod
    def administrator(cls) -> "Role":
        return cls.system(ADMINISTRATOR)

    @classmethod
    def account_manager(cls) -> "Role":
        return cls.system(ACCOUNT_MANAGER)


def _photo_path(instance: "UserProfile", filename: str) -> str:
    # Random name: a new photo gets a new address (the browser does not show the old one)
    return f"users/{uuid.uuid4().hex}{posixpath.splitext(filename)[1].lower()}"


class IdDocumentType(models.TextChoices):
    CPF = "cpf", "CPF"
    RG = "rg", "RG"
    NATIONAL_ID = "national_id", _("National ID")
    PASSPORT = "passport", _("Passport")
    OTHER = "other", _("Other")


class UserProfile(PhotoMixin, models.Model):
    """What the app keeps about a user besides Django's user: photo (square, shown in a circle),
    employee data and, for account managers, the business verticals they work in. Every user
    has one (created with the user)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("user"),
    )
    photo = models.FileField(_("photo"), upload_to=_photo_path, max_length=255, blank=True)

    # Identification
    id_document_type = models.CharField(
        _("identity document type"), max_length=20, choices=IdDocumentType, blank=True
    )
    # Uppercase letters and digits only (CPF validated)
    id_document_number = models.CharField(_("identity document number"), max_length=40, blank=True)
    employee_number = models.CharField(_("employee number"), max_length=30, blank=True)
    nationality = models.CharField(_("nationality"), max_length=2, blank=True)  # ISO 3166-1
    birth_date = models.DateField(_("birth date"), null=True, blank=True)

    # Employment
    job_title = models.CharField(_("job title"), max_length=100, blank=True)
    department = models.CharField(_("department"), max_length=100, blank=True)
    work_location = models.CharField(_("work location"), max_length=100, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="direct_reports",
        verbose_name=_("manager"),
    )
    hire_date = models.DateField(_("hire date"), null=True, blank=True)
    phone = models.CharField(_("phone"), max_length=30, blank=True)
    mobile_phone = models.CharField(_("mobile phone"), max_length=30, blank=True)
    keywords = keywords_field()

    # Account managers: the business verticals they work in (all their sub-verticals)
    verticals = models.ManyToManyField(
        "catalogs.Vertical",
        blank=True,
        related_name="account_manager_profiles",
        verbose_name=_("business verticals"),
    )

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")
        constraints = [
            models.UniqueConstraint(
                fields=["employee_number"],
                condition=~models.Q(employee_number=""),
                name="profile_unique_employee_number",
            ),
            models.UniqueConstraint(
                fields=["id_document_type", "id_document_number"],
                condition=~models.Q(id_document_number=""),
                name="profile_unique_id_document",
            ),
        ]

    def __str__(self):
        return str(self.user)

    @classmethod
    def for_user(cls, user) -> "UserProfile":
        profile, _created = cls.objects.get_or_create(user=user)
        return profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _create_profile(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        UserProfile.objects.get_or_create(user=instance)


def is_account_manager(user) -> bool:
    return user.roles.filter(key=ACCOUNT_MANAGER).exists()


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
