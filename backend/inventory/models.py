import posixpath
import uuid

from django.conf import settings
from django.db import models, transaction
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
    # Where it came from: the receiving lot and the customer who returned it (the contract is
    # identified later, by the serial number)
    lot = models.ForeignKey(
        "ReceivingLot",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
        verbose_name=_("lot"),
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="returned_assets",
        verbose_name=_("customer"),
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
    # Accessories tracked by quantity: the model, how many and in which condition
    accessory_model = models.ForeignKey(
        "catalogs.AssetModel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("accessory model"),
    )
    quantity = models.PositiveIntegerField(_("quantity"), null=True, blank=True)
    accessory_condition = models.CharField(max_length=10, blank=True)
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
            # Exactly one of: an asset, a container, an accessory balance
            models.CheckConstraint(
                condition=models.Q(
                    asset__isnull=False, container__isnull=True, accessory_model__isnull=True
                )
                | models.Q(
                    asset__isnull=True, container__isnull=False, accessory_model__isnull=True
                )
                | models.Q(
                    asset__isnull=True,
                    container__isnull=True,
                    accessory_model__isnull=False,
                    quantity__gt=0,
                ),
                name="event_asset_container_or_accessory",
            ),
        ]

    def __str__(self):
        target = self.asset or self.container or f"{self.accessory_model} × {self.quantity}"
        return f"{self.get_kind_display()} {target}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError("Movement events cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Movement events cannot be deleted.")


# --- Phase 2: appointments, receiving lots, triage, accessory balances, occurrences ----------


def yearly_code(prefix: str, year: int, sequence: int) -> str:
    """ "LOT-2026-0001": prefix, year and the sequence of the year (4 digits)."""
    return f"{prefix}-{year}-{sequence:04d}"


class AppointmentKind(models.TextChoices):
    RECEIVING = "receiving", _("Receiving")
    SHIPPING = "shipping", _("Shipping")


class AppointmentStatus(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled")
    CONFIRMED = "confirmed", _("Confirmed")
    IN_PROGRESS = "in_progress", _("In Progress")
    DONE = "done", _("Done")
    CANCELLED = "cancelled", _("Cancelled")
    NO_SHOW = "no_show", _("No-Show")


class Appointment(models.Model):
    """A receiving (a customer's return, as agreed with them) or a shipping scheduled at a
    warehouse's docks. A receiving carries the expected list; its lot is opened from it when
    the vehicle arrives. Overlaps in the same warehouse are only warned about."""

    year = models.PositiveSmallIntegerField(_("year"))
    sequence = models.PositiveIntegerField(_("sequence"))
    kind = models.CharField(_("kind"), max_length=10, choices=AppointmentKind.choices)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name=_("warehouse"),
    )
    # Required for receivings (who returns); optional for shippings (the buyer may be anyone)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name=_("customer"),
    )
    starts_at = models.DateTimeField(_("starts at"))
    ends_at = models.DateTimeField(_("ends at"))
    status = models.CharField(
        _("status"),
        max_length=12,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED,
    )
    # Carrier: a provider of transport, or a name when it is not registered
    carrier = models.ForeignKey(
        "service_providers.ServiceProvider",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name=_("carrier"),
    )
    carrier_name = models.CharField(_("carrier name"), max_length=150, blank=True)
    vehicle_plate = models.CharField(_("vehicle plate"), max_length=20, blank=True)
    driver_name = models.CharField(_("driver"), max_length=150, blank=True)
    expected_volumes = models.PositiveIntegerField(_("expected volumes"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("appointment")
        verbose_name_plural = _("appointments")
        ordering = ["starts_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["year", "sequence"], name="appointment_unique_code"),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="appointment_ends_after_start",
            ),
        ]

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        return yearly_code("APT", self.year, self.sequence)


class ExpectedItem(models.Model):
    """A line of a receiving's expected list (what the customer agreed to return): a model, an
    optional serial number (then the quantity is 1) and a quantity. Never shown to the receivers
    who count (blind count, RN-17)."""

    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="expected_items"
    )
    asset_model = models.ForeignKey(
        "catalogs.AssetModel",
        on_delete=models.PROTECT,
        related_name="expected_items",
        verbose_name=_("asset model"),
    )
    serial = models.CharField(_("serial number"), max_length=100, blank=True)
    quantity = models.PositiveIntegerField(_("quantity"), default=1)

    class Meta:
        verbose_name = _("expected item")
        verbose_name_plural = _("expected items")
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="expected_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(serial="") | models.Q(quantity=1),
                name="expected_item_one_per_serial",
            ),
        ]

    def __str__(self):
        return f"{self.asset_model} {self.serial or f'× {self.quantity}'}"


class LotStatus(models.TextChoices):
    OPEN = "open", _("Open")
    RECONCILING = "reconciling", _("Reconciling")
    CLOSED = "closed", _("Closed")


class ReceivingLot(models.Model):
    """One arrival at a warehouse: a customer's return (with assets of any of their contracts —
    identified later by serial number), triaged at a dock. Opened from a receiving appointment
    (then reconciled against its expected list) or unscheduled."""

    year = models.PositiveSmallIntegerField(_("year"))
    sequence = models.PositiveIntegerField(_("sequence"))
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="lots", verbose_name=_("warehouse")
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="receiving_lots",
        verbose_name=_("customer"),
    )
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lot",
        verbose_name=_("appointment"),
    )
    # Where the triage happens (an area of the Dock kind of the lot's warehouse)
    dock = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="+", verbose_name=_("dock")
    )
    fiscal_document_number = models.CharField(
        _("fiscal document number"), max_length=60, blank=True
    )
    status = models.CharField(
        _("status"), max_length=12, choices=LotStatus.choices, default=LotStatus.OPEN
    )
    notes = models.TextField(_("notes"), blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    opened_at = models.DateTimeField(_("opened at"), auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)

    class Meta:
        verbose_name = _("receiving lot")
        verbose_name_plural = _("receiving lots")
        ordering = ["-opened_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["year", "sequence"], name="lot_unique_code"),
        ]

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        return yearly_code("LOT", self.year, self.sequence)

    @property
    def is_scheduled(self) -> bool:
        """It had an expected list (then it is reconciled against it)."""
        return self.appointment_id is not None and self.appointment.expected_items.exists()


def _attachment_path(instance: "LotAttachment", filename: str) -> str:
    # Random stored name (the original one is kept in `name`), one folder per lot
    ext = posixpath.splitext(filename)[1].lower()
    return f"inventory/lots/{instance.lot_id}/{uuid.uuid4().hex}{ext}"


class AttachmentKind(models.TextChoices):
    FISCAL_DOCUMENT = "fiscal_document", _("Fiscal Document")
    PACKAGE_PHOTO = "package_photo", _("Package Photo")
    DAMAGE_PHOTO = "damage_photo", _("Damage Photo")
    NO_SERIAL_PHOTO = "no_serial_photo", _("Photo Without Serial Number")
    OCCURRENCE = "occurrence", _("Occurrence Evidence")
    OTHER = "other", _("Other")


class LotAttachment(models.Model):
    """A file of a lot: its fiscal document, photos of the packages or damage, the photo of an
    asset whose serial could not be read, an occurrence's evidence. Deleting it removes the file."""

    lot = models.ForeignKey(ReceivingLot, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(_("kind"), max_length=20, choices=AttachmentKind.choices)
    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments"
    )
    occurrence = models.ForeignKey(
        "Occurrence", on_delete=models.CASCADE, null=True, blank=True, related_name="attachments"
    )
    file = models.FileField(_("file"), upload_to=_attachment_path, max_length=255)
    name = models.CharField(_("name"), max_length=255)
    size = models.PositiveBigIntegerField(_("size (bytes)"))
    content_type = models.CharField(_("content type"), max_length=100)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("lot attachment")
        verbose_name_plural = _("lot attachments")
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        storage, path = self.file.storage, self.file.name
        result = super().delete(*args, **kwargs)
        transaction.on_commit(lambda: storage.delete(path))
        return result


class AccessoryCondition(models.TextChoices):
    GOOD = "good", _("Good")
    SCRAP = "scrap", _("Scrap")


class AccessoryBalance(models.Model):
    """How many units of a low-value accessory model (tracked by quantity) are in a container or
    at a location, in good condition or as scrap. Never negative (RN-06); changed only by
    inventory.services (with an event)."""

    asset_model = models.ForeignKey(
        "catalogs.AssetModel",
        on_delete=models.PROTECT,
        related_name="balances",
        verbose_name=_("asset model"),
    )
    container = models.ForeignKey(
        Container, on_delete=models.PROTECT, null=True, blank=True, related_name="balances"
    )
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True, related_name="balances"
    )
    condition = models.CharField(
        _("condition"),
        max_length=10,
        choices=AccessoryCondition.choices,
        default=AccessoryCondition.GOOD,
    )
    quantity = models.IntegerField(_("quantity"), default=0)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("accessory balance")
        verbose_name_plural = _("accessory balances")
        ordering = ["asset_model__name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="balance_never_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(container__isnull=False, location__isnull=True)
                | models.Q(container__isnull=True, location__isnull=False),
                name="balance_in_container_or_location",
            ),
            models.UniqueConstraint(
                fields=["asset_model", "container", "condition"],
                condition=models.Q(container__isnull=False),
                name="balance_unique_in_container",
            ),
            models.UniqueConstraint(
                fields=["asset_model", "location", "condition"],
                condition=models.Q(location__isnull=False),
                name="balance_unique_at_location",
            ),
        ]

    def __str__(self):
        return f"{self.asset_model} × {self.quantity}"

    @property
    def place(self) -> Location:
        return self.container.current_location if self.container_id else self.location


class OccurrenceKind(models.TextChoices):
    SHORTAGE = "shortage", _("Shortage")
    SURPLUS = "surplus", _("Surplus")
    SERIAL_MISMATCH = "serial_mismatch", _("Serial Number Mismatch")
    MODEL_MISMATCH = "model_mismatch", _("Model Mismatch")
    TRANSPORT_DAMAGE = "transport_damage", _("Transport Damage")
    LOCATION_MISMATCH = "location_mismatch", _("Location Mismatch")
    LOST = "lost", _("Lost")


class OccurrenceStatus(models.TextChoices):
    OPEN = "open", _("Open")
    RESOLVED = "resolved", _("Resolved")
    ACCEPTED = "accepted", _("Accepted")


class Occurrence(models.Model):
    """Something wrong found in a lot (later also in a transfer): a shortage, a surplus, a
    different serial or model, transport damage… Created by the reconciliation (`automatic`) or
    by hand. A lot closes only when all are resolved or accepted (RN-18; accepting is for
    inventory supervisors)."""

    kind = models.CharField(_("kind"), max_length=20, choices=OccurrenceKind.choices)
    lot = models.ForeignKey(
        ReceivingLot,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="occurrences",
        verbose_name=_("lot"),
    )
    asset = models.ForeignKey(
        Asset, on_delete=models.PROTECT, null=True, blank=True, related_name="occurrences"
    )
    asset_model = models.ForeignKey(
        "catalogs.AssetModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    quantity = models.PositiveIntegerField(_("quantity"), default=1)
    expected_serial = models.CharField(_("expected serial number"), max_length=100, blank=True)
    received_serial = models.CharField(_("received serial number"), max_length=100, blank=True)
    description = models.TextField(_("description"), blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    due_date = models.DateField(_("due date"), null=True, blank=True)
    status = models.CharField(
        _("status"), max_length=10, choices=OccurrenceStatus.choices, default=OccurrenceStatus.OPEN
    )
    resolution = models.TextField(_("resolution"), blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    # Created by the reconciliation (replaced when it runs again, while still open)
    automatic = models.BooleanField(_("automatic"), default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("occurrence")
        verbose_name_plural = _("occurrences")
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.lot})"
