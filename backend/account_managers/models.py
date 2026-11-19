import posixpath
import uuid

from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from config.photos import PhotoMixin, remove_file_later


def _photo_path(instance: "AccountManager", filename: str) -> str:
    # Random name: a new photo gets a new address (the browser does not show the old one)
    return f"account-managers/{uuid.uuid4().hex}{posixpath.splitext(filename)[1].lower()}"


class AccountManager(PhotoMixin, models.Model):
    first_name = models.CharField(_("first name"), max_length=100)
    last_name = models.CharField(_("last name"), max_length=100, blank=True)
    # "First Last", kept up to date on save (for search, sorting and other modules)
    full_name = models.CharField(_("full name"), max_length=201, editable=False)
    email = models.EmailField(_("email"), max_length=254)
    # The business verticals this account manager works in (all their sub-verticals)
    verticals = models.ManyToManyField(
        "catalogs.Vertical",
        blank=True,
        related_name="account_managers",
        verbose_name=_("business verticals"),
    )
    # Square picture (the browser crops and resizes it before sending), shown in a circle
    photo = models.FileField(_("photo"), upload_to=_photo_path, max_length=255, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("account manager")
        verbose_name_plural = _("account managers")
        ordering = ["full_name"]
        constraints = [
            # One account manager per email, regardless of letter case
            models.UniqueConstraint(Lower("email"), name="account_manager_unique_email"),
        ]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    def save(self, *args, **kwargs):
        self.full_name = " ".join(f"{self.first_name} {self.last_name}".split())
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and {"first_name", "last_name"} & set(update_fields):
            kwargs["update_fields"] = {*update_fields, "full_name"}
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        storage, old = self.photo.storage, self.photo.name
        result = super().delete(*args, **kwargs)
        remove_file_later(storage, old)
        return result
