from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from entities.models import EntityRoleModel


class ContractType(models.TextChoices):
    """How a customer takes Horizon's assets or services ("Modalidades"; several per customer,
    none while only a prospect). Selling goods is not one: buyers are a role of their own."""

    RENTER = "renter", _("Renter")
    LESSEE = "lessee", _("Lessee")
    BAILEE = "bailee", _("Bailee (Free Loan)")
    SERVICE_CUSTOMER = "service_customer", _("Service Customer")


class Customer(EntityRoleModel):
    """The Customer role of a business entity (company or person): the commercial
    relationship — its account managers, eFMV analyses — and its contract types (renter,
    lessee…). Its identification, contact and address are the entity's (`customer.name`)."""

    # ContractType values, in the choices' order; none while only a prospect
    contract_types = ArrayField(
        models.CharField(max_length=30, choices=ContractType.choices),
        default=list,
        blank=True,
        verbose_name=_("contract types"),
    )

    # Exactly one primary account manager and any number of secondary ones — users with the
    # "Account Manager" role. Such a user cannot be deleted nor lose the role.
    primary_account_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="primary_customers",
        verbose_name=_("primary account manager"),
    )
    secondary_account_managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="secondary_customers",
        verbose_name=_("secondary account managers"),
    )

    class Meta(EntityRoleModel.Meta):
        verbose_name = _("customer")
        verbose_name_plural = _("customers")
