from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from entities.models import EntityRoleModel


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


class ServiceProvider(EntityRoleModel):
    """The Service Provider role of a business entity: warehousing, transport, refurbishment…
    Its identification, contact and address are the entity's (`provider.name` reads it)."""

    entity = models.OneToOneField(
        "entities.BusinessEntity",
        on_delete=models.CASCADE,
        related_name="service_provider",
        verbose_name=_("business entity"),
    )
    # Services it can provide (ServiceKind values, at least one, in the choices' order)
    services = ArrayField(
        models.CharField(max_length=30, choices=ServiceKind.choices),
        default=list,
        verbose_name=_("services"),
    )

    class Meta(EntityRoleModel.Meta):
        verbose_name = _("service provider")
        verbose_name_plural = _("service providers")

    def provides(self, kind: str) -> bool:
        return kind in self.services
