from django.db import models
from django.utils.translation import gettext_lazy as _

from account_managers.models import AccountManager


class Customer(models.Model):
    """A lessee: company (CNPJ) or individual (CPF) that signs leasing contracts."""

    # Identification
    name = models.CharField(_("legal name"), max_length=200)
    trade_name = models.CharField(_("trade name"), max_length=200, blank=True)
    # CNPJ/CPF in Brazil (validated); other countries' tax IDs are free-form.
    # Always stored uppercase without punctuation.
    tax_id = models.CharField(_("tax ID"), max_length=20)
    country = models.CharField(_("country"), max_length=2, default="BR")  # ISO 3166-1 alpha-2

    # Contact
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=30, blank=True)

    # Address
    postal_code = models.CharField(_("postal code"), max_length=10, blank=True)
    street = models.CharField(_("street"), max_length=200, blank=True)
    number = models.CharField(_("number"), max_length=20, blank=True)
    complement = models.CharField(_("complement"), max_length=100, blank=True)
    district = models.CharField(_("district"), max_length=100, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    state = models.CharField(_("state"), max_length=50, blank=True)

    # Relationship: exactly one primary account manager and any number of secondary ones.
    # An account manager linked to customers (either way) cannot be deleted.
    primary_account_manager = models.ForeignKey(
        AccountManager,
        on_delete=models.PROTECT,
        related_name="primary_customers",
        verbose_name=_("primary account manager"),
    )
    secondary_account_managers = models.ManyToManyField(
        AccountManager,
        blank=True,
        related_name="secondary_customers",
        verbose_name=_("secondary account managers"),
    )
    is_active = models.BooleanField(_("active"), default=True)
    notes = models.TextField(_("notes"), blank=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["country", "tax_id"], name="customer_unique_tax_id"),
        ]

    def __str__(self):
        return self.name
