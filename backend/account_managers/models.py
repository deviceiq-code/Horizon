import posixpath
import uuid

from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _


def _photo_path(instance: "AccountManager", filename: str) -> str:
    # Random name: a new photo gets a new address (the browser does not show the old one)
    return f"account-managers/{uuid.uuid4().hex}{posixpath.splitext(filename)[1].lower()}"


class AccountManager(models.Model):
    full_name = models.CharField(_("full name"), max_length=150)
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

    def set_photo(self, content) -> None:
        """Store a new photo (replacing the previous file) or remove it (content=None)."""
        old = self.photo.name
        if content is None:
            self.photo = ""
        else:
            self.photo.save(content.name, content, save=False)
        self.save(update_fields=["photo", "updated_at"])
        self._remove_file_later(old)

    def delete(self, *args, **kwargs):
        old = self.photo.name
        result = super().delete(*args, **kwargs)
        self._remove_file_later(old)
        return result

    def _remove_file_later(self, name: str) -> None:
        if name:
            storage = self.photo.storage
            # Only once the change is committed
            transaction.on_commit(lambda: storage.delete(name))
