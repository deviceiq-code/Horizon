from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from config.keywords import keywords_field


class ServiceKind(models.TextChoices):
    """What a service provider can do for Horizon (several per provider). The list is fixed:
    rules depend on some kinds (e.g. only providers of warehousing run outsourced warehouses)."""

    WAREHOUSING = "warehousing", _("Warehousing")
    TRANSPORT = "transport", _("Transport and Logistics")
    INSPECTION = "inspection", _("Inspection and Appraisal")
    REFURBISHMENT = "refurbishment", _("Refurbishment")
    REPAIR = "repair", _("Maintenance and Repair")
    DATA_ERASURE = "data_erasure", _("Data Erasure")
    PACKAGING = "packaging", _("Packaging")
    SALES = "sales", _("Sales and Auctions")
    DISPOSAL = "disposal", _("Disposal and Recycling")


class ServiceProvider(models.Model):
    """A company (or person) that provides services: warehousing, transport, refurbishment…"""

    # Identification (as customers')
    name = models.CharField(_("legal name"), max_length=200)
    trade_name = models.CharField(_("trade name"), max_length=200, blank=True)
    # CNPJ/CPF in Brazil (validated); other countries' tax IDs are free-form.
    # Always stored uppercase without punctuation.
    tax_id = models.CharField(_("tax ID"), max_length=20)
    country = models.CharField(_("country"), max_length=2, default="BR")  # ISO 3166-1 alpha-2

    # Services it can provide (ServiceKind values, at least one, in the choices' order)
    services = ArrayField(
        models.CharField(max_length=30, choices=ServiceKind.choices),
        default=list,
        verbose_name=_("services"),
    )

    # Contact
    contact_name = models.CharField(_("contact name"), max_length=150, blank=True)
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

    is_active = models.BooleanField(_("active"), default=True)
    notes = models.TextField(_("notes"), blank=True)
    keywords = keywords_field()

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("service provider")
        verbose_name_plural = _("service providers")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["country", "tax_id"], name="service_provider_unique_tax_id"
            ),
        ]

    def __str__(self):
        return self.trade_name or self.name

    def provides(self, kind: str) -> bool:
        return kind in self.services
