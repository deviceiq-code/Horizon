from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from config.keywords import keywords_field

from .codes import next_warehouse_code, warehouse_code_prefix
from .states import AreaType, AssetStatus


class Ownership(models.TextChoices):
    """Who runs the warehouse: Horizon itself or a service provider of warehousing."""

    OWN = "own", _("Own")
    OUTSOURCED = "outsourced", _("Outsourced")


class Warehouse(models.Model):
    """A stock location of Remarketing: where returned equipment is received and kept until it
    is made available to buyers of used assets."""

    name = models.CharField(_("name"), max_length=100)
    # Generated on creation ("SP01": state or country + number) and never changed: it starts
    # the codes of the warehouse's locations, printed on their labels
    code = models.CharField(_("code"), max_length=12, unique=True, editable=False)
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

    def save(self, *args, **kwargs):
        if not self.code:
            prefix = warehouse_code_prefix(self.state, self.country)
            taken = set(
                Warehouse.objects.filter(code__startswith=prefix).values_list("code", flat=True)
            )
            self.code = next_warehouse_code(prefix, taken)
        super().save(*args, **kwargs)


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


class Location(models.Model):
    """A physical address in a warehouse — area → aisle → shelf → position, as a tree — or the
    global virtual location of assets in transit between warehouses.

    The code is the parent's (or the warehouse's) code + "-" + the segment typed by the user
    ("SP01-EST-03-B"); it is printed on the location's label. The area type says which asset
    statuses it takes (inventory.states.AREA_STATUSES); children start with their parent's.
    """

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="locations",
        verbose_name=_("warehouse"),
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("parent location"),
    )
    segment = models.CharField(_("segment"), max_length=20)
    code = models.CharField(_("code"), max_length=80, unique=True)
    area_type = models.CharField(_("area type"), max_length=20, choices=AreaType.choices)
    description = models.CharField(_("description"), max_length=150, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("location")
        verbose_name_plural = _("locations")
        ordering = ["code"]
        constraints = [
            # Only the virtual transit location has no warehouse
            models.CheckConstraint(
                condition=models.Q(warehouse__isnull=False)
                | models.Q(area_type=AreaType.VIRTUAL_TRANSIT),
                name="location_warehouse_unless_virtual",
            ),
        ]

    def __str__(self):
        return self.code

    @property
    def is_virtual(self) -> bool:
        return self.area_type == AreaType.VIRTUAL_TRANSIT

    @classmethod
    def transit(cls) -> "Location":
        """The global virtual location of assets travelling between warehouses."""
        return cls.objects.get(code=TRANSIT_CODE)


TRANSIT_CODE = "VIRTUAL-TRANSIT"


class ContainerKind(models.TextChoices):
    BOX = "box", _("Box")
    CAGE = "cage", _("Cage")
    PALLET = "pallet", _("Pallet")


class Container(models.Model):
    """A box, cage or pallet with its own code ("C" + 8 digits + check digit): moving it moves
    everything inside."""

    code = models.CharField(_("code"), max_length=12, unique=True, editable=False)
    kind = models.CharField(_("kind"), max_length=10, choices=ContainerKind.choices)
    current_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="containers",
        verbose_name=_("current location"),
    )
    description = models.CharField(_("description"), max_length=150, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("container")
        verbose_name_plural = _("containers")
        ordering = ["code"]

    def __str__(self):
        return self.code


class SerialStatus(models.TextChoices):
    CAPTURED = "captured", _("Captured")
    PENDING = "pending", _("Pending")
    NONE = "none", _("No Serial Number")


class NoSerialReason(models.TextChoices):
    UNREADABLE = "unreadable", _("Unreadable or Missing")
    NEEDS_POWER_ON = "needs_power_on", _("Needs to Be Turned On")
    ITEM_HAS_NONE = "item_has_none", _("Item Has No Serial Number")


class Asset(models.Model):
    """A physical unit in stock, identified by its Horizon ID (printed on its label), whatever
    its serial number. There is no customer asset tag (business decision).

    `status`, `current_location` and `current_container` mirror its latest movement event:
    only inventory.services changes them (RN-07).
    """

    horizon_id = models.CharField(_("Horizon ID"), max_length=12, unique=True)
    asset_model = models.ForeignKey(
        "catalogs.AssetModel",
        on_delete=models.PROTECT,
        related_name="assets",
        verbose_name=_("asset model"),
    )
    # Its own values of the asset class's template (start as the model's)
    specs = models.JSONField(_("specifications"), default=list, blank=True)
    serial = models.CharField(_("serial number"), max_length=100, blank=True)
    serial_status = models.CharField(
        _("serial number status"), max_length=10, choices=SerialStatus.choices
    )
    no_serial_reason = models.CharField(
        _("reason for no serial number"),
        max_length=20,
        choices=NoSerialReason.choices,
        blank=True,
    )
    # Other identifiers: {"imei": …, "mac": …, "service_tag": …}
    other_ids = models.JSONField(_("other identifiers"), default=dict, blank=True)
    status = models.CharField(_("status"), max_length=20, choices=AssetStatus.choices)
    current_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="assets",
        verbose_name=_("current location"),
    )
    current_container = models.ForeignKey(
        Container,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
        verbose_name=_("current container"),
    )
    # The status it had when it went in transit (it comes back to it at the destination)
    status_before_transit = models.CharField(max_length=20, choices=AssetStatus.choices, blank=True)
    held_for_dispute = models.BooleanField(_("held for dispute"), default=False)
    # Parts taken from it and disks removed for destruction point to it
    parent_asset = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="parts",
        verbose_name=_("parent asset"),
    )
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("created by"),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("asset")
        verbose_name_plural = _("assets")
        ordering = ["horizon_id"]
        constraints = [
            # RN-05: a captured serial is unique within its model
            models.UniqueConstraint(
                "asset_model",
                "serial",
                condition=models.Q(serial_status="captured"),
                name="asset_unique_serial_per_model",
            ),
            models.CheckConstraint(
                condition=models.Q(serial_status="captured", no_serial_reason="")
                | (~models.Q(serial_status="captured") & ~models.Q(no_serial_reason="")),
                name="asset_reason_unless_serial_captured",
            ),
        ]

    def __str__(self):
        return self.horizon_id


class LabelRange(models.Model):
    """Horizon IDs reserved to print labels in advance; reading one at triage binds it to the
    asset (an ID is bound only once)."""

    first_number = models.PositiveIntegerField(_("first number"))
    last_number = models.PositiveIntegerField(_("last number"))
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("reserved by"),
    )
    reserved_at = models.DateTimeField(_("reserved at"), auto_now_add=True)

    class Meta:
        verbose_name = _("label range")
        verbose_name_plural = _("label ranges")
        ordering = ["-reserved_at"]

    def __str__(self):
        return f"{self.first_number}–{self.last_number}"

    @property
    def size(self) -> int:
        return self.last_number - self.first_number + 1


class EventKind(models.TextChoices):
    ENTRY = "entry", _("Entry")
    PUTAWAY = "putaway", _("Put-Away")
    RELOCATION = "relocation", _("Relocation")
    STATUS_CHANGE = "status_change", _("Status Change")
    PICKING = "picking", _("Picking")
    SHIPPING = "shipping", _("Shipping")
    TRANSFER_OUT = "transfer_out", _("Transfer Out")
    TRANSFER_IN = "transfer_in", _("Transfer In")
    INVENTORY_ADJUSTMENT = "inventory_adjustment", _("Inventory Adjustment")
    REVERSAL = "reversal", _("Reversal")
    LABEL_REPRINT = "label_reprint", _("Label Reprint")


class ImmutableError(Exception):
    pass


class MovementEvent(models.Model):
    """The audit trail: what happened to an asset or a container, where, by whom and when.

    Immutable — never updated nor deleted; a correction is a new REVERSAL event pointing to the
    original. A container's move is one event for the container plus one child event per asset
    inside (`parent_event`), so each asset's history is complete on its own (RN-08).
    """

    kind = models.CharField(_("kind"), max_length=25, choices=EventKind.choices)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
        verbose_name=_("asset"),
    )
    container = models.ForeignKey(
        Container,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
        verbose_name=_("container"),
    )
    from_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    to_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    from_container = models.ForeignKey(
        Container, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    to_container = models.ForeignKey(
        Container, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status_before = models.CharField(max_length=20, choices=AssetStatus.choices, blank=True)
    status_after = models.CharField(max_length=20, choices=AssetStatus.choices, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField(_("date and time"), auto_now_add=True)
    reason = models.CharField(_("reason"), max_length=300, blank=True)
    # What caused it, as "<kind>:<id>" (lot, inspection report, transfer, disposal…)
    document_ref = models.CharField(_("document"), max_length=60, blank=True)
    parent_event = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="child_events"
    )
    reverses = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals"
    )

    class Meta:
        verbose_name = _("movement event")
        verbose_name_plural = _("movement events")
        ordering = ["at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(asset__isnull=False, container__isnull=True)
                | models.Q(asset__isnull=True, container__isnull=False),
                name="event_asset_or_container",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.asset or self.container}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError("Movement events cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Movement events cannot be deleted.")
