"""Business Entities: every company or person Horizon deals with (docs/business-entities.md).

What they all have in common lives in `BusinessEntity`; each kind of relationship is a role —
a table 1:1 with the entity, with its own active flag and data. Customers and service providers
are roles too (`customers.Customer`, `service_providers.ServiceProvider`), kept in their apps so
the records pointing to them stay as they are.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from config.audit import created_by_field, updated_by_field
from config.keywords import keywords_field


class EntityRole(models.TextChoices):
    """The roles an entity may have, in the order the page's tabs show them. The value is the
    name of the role's relation on the entity (`entity.customer`, `entity.buyer`…)."""

    CUSTOMER = "customer", _("Customer")
    SUPPLIER = "supplier", _("Supplier")
    SERVICE_PROVIDER = "service_provider", _("Service Provider")
    BUYER = "buyer", _("Buyer")


class BusinessEntity(models.Model):
    """A company (CNPJ) or a person (CPF) — anywhere — and its head office, when it has one."""

    # Identification
    name = models.CharField(_("legal name"), max_length=200)
    trade_name = models.CharField(_("trade name"), max_length=200, blank=True)
    # CNPJ/CPF in Brazil (validated); other countries' tax IDs are free-form.
    # Always stored uppercase without punctuation.
    tax_id = models.CharField(_("tax ID"), max_length=20)
    country = models.CharField(_("country"), max_length=2, default="BR")  # ISO 3166-1 alpha-2
    # Its head office (another entity); the tree under one without it is a group
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="branches",
        verbose_name=_("head office"),
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
    created_by = created_by_field()
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by = updated_by_field()

    class Meta:
        verbose_name = _("business entity")
        verbose_name_plural = _("business entities")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["country", "tax_id"], name="entity_unique_tax_id"),
        ]

    def __str__(self):
        return self.trade_name or self.name

    @property
    def display_name(self) -> str:
        return self.trade_name or self.name

    def role(self, role: str):
        """The entity's role (its row) or None."""
        try:
            return getattr(self, role)
        except models.ObjectDoesNotExist:
            return None

    def roles(self) -> list[str]:
        """The roles it has, in the tabs' order."""
        return [role for role in EntityRole.values if self.role(role) is not None]


ENTITY_FIELDS = {
    "name", "trade_name", "tax_id", "country", "parent", "contact_name", "email", "phone",
    "postal_code", "street", "number", "complement", "district", "city", "state", "notes",
    "keywords",
}  # fmt: skip


class RoleManager(models.Manager):
    """`create` also takes the entity's fields (name, tax_id…) instead of `entity`: the entity
    with that country and tax ID is used, or created with them (scripts and tests)."""

    def create(self, **kwargs):
        entity_fields = {key: kwargs.pop(key) for key in list(kwargs) if key in ENTITY_FIELDS}
        if entity_fields and "entity" not in kwargs:
            country = entity_fields.get("country", "BR")
            tax_id = entity_fields.get("tax_id", "")
            entity = (
                BusinessEntity.objects.filter(country=country, tax_id=tax_id).first()
                if tax_id
                else None
            )
            if entity is None:
                entity = BusinessEntity.objects.create(**entity_fields)
            kwargs["entity"] = entity
        return super().create(**kwargs)


class EntityRoleModel(models.Model):
    """What every role has: its entity (1:1), whether it is active in the role, and when.
    The entity's identification, contact and address read through it (`customer.name`)."""

    entity = models.OneToOneField(
        BusinessEntity,
        on_delete=models.CASCADE,
        related_name="%(class)s",
        verbose_name=_("business entity"),
    )
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = RoleManager()

    class Meta:
        abstract = True
        ordering = ["entity__name"]

    def __str__(self):
        return str(self.entity)

    # The entity's fields, read through the role (as when they lived in it)
    name = property(lambda self: self.entity.name)
    trade_name = property(lambda self: self.entity.trade_name)
    tax_id = property(lambda self: self.entity.tax_id)
    country = property(lambda self: self.entity.country)
    contact_name = property(lambda self: self.entity.contact_name)
    email = property(lambda self: self.entity.email)
    phone = property(lambda self: self.entity.phone)
    postal_code = property(lambda self: self.entity.postal_code)
    street = property(lambda self: self.entity.street)
    number = property(lambda self: self.entity.number)
    complement = property(lambda self: self.entity.complement)
    district = property(lambda self: self.entity.district)
    city = property(lambda self: self.entity.city)
    state = property(lambda self: self.entity.state)
    notes = property(lambda self: self.entity.notes)
    keywords = property(lambda self: self.entity.keywords)

    @property
    def is_usable(self) -> bool:
        """Active in the role and as an entity: what pickers offer."""
        return self.is_active and self.entity.is_active


class SupplyKind(models.TextChoices):
    PRODUCTS = "products", _("Products")
    SERVICES = "services", _("Services")


class Supplier(EntityRoleModel):
    """Supplies Horizon with products and/or services (more data to come)."""

    supplies = ArrayField(
        models.CharField(max_length=20, choices=SupplyKind.choices),
        default=list,
        verbose_name=_("supplies"),
    )

    class Meta(EntityRoleModel.Meta):
        verbose_name = _("supplier")
        verbose_name_plural = _("suppliers")


class Buyer(EntityRoleModel):
    """Buys used assets (Remarketing; third-party sales of the inventory's disposals)."""

    class Meta(EntityRoleModel.Meta):
        verbose_name = _("buyer")
        verbose_name_plural = _("buyers")
