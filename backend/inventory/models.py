from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from config.keywords import keywords_field


class Ownership(models.TextChoices):
    """Who runs the warehouse: Horizon itself or a service provider of warehousing."""

    OWN = "own", _("Own")
    OUTSOURCED = "outsourced", _("Outsourced")


class Warehouse(models.Model):
    """A stock location of Remarketing: where returned equipment is received and kept until it
    is made available to buyers of used assets."""

    name = models.CharField(_("name"), max_length=100)
    ownership = models.CharField(
        _("ownership"), max_length=20, choices=Ownership.choices, default=Ownership.OWN
    )
    # Outsourced only (required then): a provider offering warehousing
    service_provider = models.ForeignKey(
        "service_providers.ServiceProvider",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="warehouses",
        verbose_name=_("service provider"),
    )

    # Business verticals whose equipment it can receive (at least one; see WarehouseVertical)
    verticals = models.ManyToManyField(
        "catalogs.Vertical",
        through="WarehouseVertical",
        related_name="warehouses",
        verbose_name=_("business verticals"),
    )

    # Contact on site
    contact_name = models.CharField(_("contact name"), max_length=150, blank=True)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=30, blank=True)

    # Address
    country = models.CharField(_("country"), max_length=2, default="BR")  # ISO 3166-1 alpha-2
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
        verbose_name = _("warehouse")
        verbose_name_plural = _("warehouses")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="warehouse_unique_name"),
            # Outsourced ⇔ run by a service provider
            models.CheckConstraint(
                condition=(
                    models.Q(ownership="own", service_provider__isnull=True)
                    | models.Q(ownership="outsourced", service_provider__isnull=False)
                ),
                name="warehouse_provider_when_outsourced",
            ),
        ]

    def __str__(self):
        return self.name


class WarehouseVertical(models.Model):
    """A vertical a warehouse serves. PROTECT: a vertical served by warehouses is not deleted."""

    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    vertical = models.ForeignKey("catalogs.Vertical", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["warehouse", "vertical"], name="warehouse_vertical"),
        ]

    def __str__(self):
        return f"{self.warehouse} — {self.vertical}"
