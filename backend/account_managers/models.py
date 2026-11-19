from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _


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
