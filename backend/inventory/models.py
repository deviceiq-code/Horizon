import posixpath
import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from catalogs.models import PhotoKind
from config.keywords import keywords_field

from .codes import next_warehouse_code, warehouse_code_prefix
from .states import AreaType, AssetStatus


class Ownership(models.TextChoices):
    """Who runs the warehouse: Horizon itself or a service provider of warehousing."""

    OWN = "own", _("Own")
    OUTSOURCED = "outsourced", _("Outsourced")


class Warehouse(models.Model):
    """A stock location of Asset Management: where returned equipment is received and kept until it
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
    # The grade of its current inspection report ("B1C"), kept here to filter and group by
    condition_grade = models.CharField(_("grade"), max_length=3, blank=True)
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
    # Or of a transfer between warehouses (shortage, surplus, damage at the arrival)
    transfer = models.ForeignKey(
        "Transfer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="occurrences",
        verbose_name=_("transfer"),
    )
    # Or of an inventory count (an asset lost); none: found while moving (RN-19)
    count = models.ForeignKey(
        "InventoryCount",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="occurrences",
        verbose_name=_("inventory count"),
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
        return f"{self.get_kind_display()} ({self.lot or self.transfer or self.count or '-'})"


# --- Phase 3: inspection -------------------------------------------------------------------


class GradeDomain(models.TextChoices):
    """The three domains of an asset's grade, written as one code ("B1C")."""

    CONSERVATION = "conservation", _("Conservation")
    FUNCTIONING = "functioning", _("Functioning")
    COMPLETENESS = "completeness", _("Completeness")


# The fixed codes of each domain (their meanings are editable: GradeLevel)
GRADE_CODES = {
    GradeDomain.CONSERVATION: ["A", "B", "C", "D"],
    GradeDomain.FUNCTIONING: ["1", "2", "3", "0"],
    GradeDomain.COMPLETENESS: ["C", "P", "I"],
}


class GradeLevel(models.Model):
    """What a level of a grade domain means (e.g. conservation "B": light marks of normal use).
    The codes are fixed (the grade code always has the same shape); descriptions are editable."""

    domain = models.CharField(_("domain"), max_length=15, choices=GradeDomain.choices)
    code = models.CharField(_("code"), max_length=1)
    name = models.CharField(_("name"), max_length=80)
    description = models.CharField(_("description"), max_length=300, blank=True)
    order = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        verbose_name = _("grade level")
        verbose_name_plural = _("grade levels")
        ordering = ["domain", "order"]
        constraints = [
            models.UniqueConstraint(fields=["domain", "code"], name="grade_level_unique_code"),
        ]

    def __str__(self):
        return f"{self.domain}:{self.code}"


class FindingKind(models.TextChoices):
    ACCESS_BLOCK = "access_block", _("Access Block")
    CUSTOMIZATION = "customization", _("Customization")
    HEAVY_CLEANING = "heavy_cleaning", _("Heavy Cleaning")
    MISSING_ITEM = "missing_item", _("Missing Item")
    DAMAGE = "damage", _("Damage Beyond Normal Wear")


class PenaltyRate(models.Model):
    """The penalty charged to customers for a kind of finding on an asset class, valid in a
    period (one table for every customer). Periods of the same class and kind never overlap
    (RN-03); a finding takes the rate valid on its report's date."""

    asset_class = models.ForeignKey(
        "catalogs.AssetClass",
        on_delete=models.PROTECT,
        related_name="penalty_rates",
        verbose_name=_("asset class"),
    )
    finding_kind = models.CharField(_("finding kind"), max_length=20, choices=FindingKind.choices)
    value = models.DecimalField(_("value"), max_digits=12, decimal_places=2)
    valid_from = models.DateField(_("valid from"))
    valid_to = models.DateField(_("valid to"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("penalty rate")
        verbose_name_plural = _("penalty rates")
        ordering = ["asset_class__name", "finding_kind", "-valid_from"]
        constraints = [
            models.CheckConstraint(condition=models.Q(value__gte=0), name="penalty_not_negative"),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gte=models.F("valid_from")),
                name="penalty_period_order",
            ),
        ]

    def __str__(self):
        return f"{self.asset_class} · {self.finding_kind}"


class ErasureMethod(models.TextChoices):
    CLEAR = "clear", _("Clear")
    PURGE = "purge", _("Purge")
    DESTROY = "destroy", _("Destroy")
    CRYPTO_ERASE = "crypto_erase", _("Cryptographic Erase")


class ErasureTool(models.Model):
    """A data erasure tool (software or equipment), its version, the methods it applies and the
    asset classes it serves."""

    name = models.CharField(_("name"), max_length=100)
    version = models.CharField(_("version"), max_length=40, blank=True)
    methods = ArrayField(
        models.CharField(max_length=15, choices=ErasureMethod.choices),
        default=list,
        verbose_name=_("methods"),
    )
    asset_classes = models.ManyToManyField(
        "catalogs.AssetClass",
        blank=True,
        related_name="erasure_tools",
        verbose_name=_("asset classes"),
    )
    notes = models.TextField(_("notes"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("erasure tool")
        verbose_name_plural = _("erasure tools")
        ordering = ["name", "version"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), Lower("version"), name="erasure_tool_unique_name_version"
            ),
        ]

    def __str__(self):
        return f"{self.name} {self.version}".strip()


class LotErasureTool(models.Model):
    """The tool and method a lot's assets of an asset class (with data storage) are erased with
    (RN-04): set by a supervisor, at the latest before their inspection erases them."""

    lot = models.ForeignKey(ReceivingLot, on_delete=models.CASCADE, related_name="erasure_tools")
    asset_class = models.ForeignKey(
        "catalogs.AssetClass", on_delete=models.PROTECT, related_name="+"
    )
    tool = models.ForeignKey(ErasureTool, on_delete=models.PROTECT, related_name="lots")
    method = models.CharField(_("method"), max_length=15, choices=ErasureMethod.choices)
    defined_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    defined_at = models.DateTimeField(_("defined at"), auto_now=True)

    class Meta:
        verbose_name = _("lot erasure tool")
        verbose_name_plural = _("lot erasure tools")
        constraints = [
            models.UniqueConstraint(fields=["lot", "asset_class"], name="lot_erasure_tool_unique"),
        ]

    def __str__(self):
        return f"{self.lot} · {self.asset_class}"


class ReportStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    AWAITING_APPROVAL = "awaiting_approval", _("Awaiting Approval")
    APPROVED = "approved", _("Approved")
    SUPERSEDED = "superseded", _("Superseded")


class Cleaning(models.TextChoices):
    STANDARD = "standard", _("Standard")
    HEAVY = "heavy", _("Heavy")


class Destination(models.TextChoices):
    AVAILABLE = "available", _("Available")
    BLOCKED = "blocked", _("Blocked")
    SCRAP = "scrap", _("Scrap")


class InspectionReport(models.Model):
    """The technical inspection of an asset, versioned: an approved report never changes
    (RN-09) — a correction is a new version and the previous one becomes superseded. Only one
    current (approved) report per asset; whoever approves is not its technician (RN-10).

    Grade: conservation (A–D) · functioning (1, 2, 3, 0 = not testable) · completeness
    (C, P, I), written "B1C" (inventory.grades)."""

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="reports")
    version = models.PositiveIntegerField(_("version"))
    is_current = models.BooleanField(_("current"), default=False)
    status = models.CharField(
        _("status"), max_length=20, choices=ReportStatus.choices, default=ReportStatus.DRAFT
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    started_at = models.DateTimeField(_("started at"), auto_now_add=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    conservation = models.CharField(_("conservation"), max_length=1, blank=True)
    functioning = models.CharField(_("functioning"), max_length=1, blank=True)
    completeness = models.CharField(_("completeness"), max_length=1, blank=True)
    failed_components = models.TextField(_("failed components"), blank=True)
    # Not working and not worth repairing → scrap
    irreparable = models.BooleanField(_("repair not viable"), default=False)
    # Kit items missing (names of the model's checklist) and the test script's results
    missing_items = models.JSONField(_("missing items"), default=list, blank=True)
    checklist_done = models.BooleanField(default=False)
    test_results = models.JSONField(_("test results"), default=dict, blank=True)
    cleaning = models.CharField(
        _("cleaning"), max_length=10, choices=Cleaning.choices, default=Cleaning.STANDARD
    )
    recommended_destination = models.CharField(
        _("recommended destination"), max_length=10, choices=Destination.choices, blank=True
    )
    notes = models.TextField(_("notes"), blank=True)
    # A supervisor sent it back to the technician (why)
    review_notes = models.TextField(_("review notes"), blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)
    sent_to_customer_at = models.DateTimeField(_("sent to customer at"), null=True, blank=True)
    # Last day the customer may dispute its findings (set when it is sent)
    dispute_deadline = models.DateField(_("dispute deadline"), null=True, blank=True)
    new_version_reason = models.TextField(_("reason for a new version"), blank=True)

    class Meta:
        verbose_name = _("inspection report")
        verbose_name_plural = _("inspection reports")
        ordering = ["asset", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["asset", "version"], name="report_unique_version"),
            models.UniqueConstraint(
                fields=["asset"],
                condition=models.Q(is_current=True),
                name="report_one_current_per_asset",
            ),
            # At most one report being prepared per asset
            models.UniqueConstraint(
                fields=["asset"],
                condition=models.Q(status__in=["draft", "awaiting_approval"]),
                name="report_one_open_per_asset",
            ),
        ]

    def __str__(self):
        return f"{self.asset} v{self.version}"

    @property
    def grade(self) -> str:
        """ "B1C" once the three domains are set ("" before)."""
        parts = (self.conservation, self.functioning, self.completeness)
        return "".join(parts) if all(parts) else ""


def _report_file_path(instance, filename: str) -> str:
    ext = posixpath.splitext(filename)[1].lower()
    return f"inventory/reports/{instance.report.asset_id}/{uuid.uuid4().hex}{ext}"


class ReportPhoto(models.Model):
    report = models.ForeignKey(InspectionReport, on_delete=models.CASCADE, related_name="photos")
    kind = models.CharField(_("kind"), max_length=10, choices=PhotoKind.choices)
    file = models.FileField(_("file"), upload_to=_report_file_path, max_length=255)
    name = models.CharField(_("name"), max_length=255)
    size = models.PositiveBigIntegerField(_("size (bytes)"))
    content_type = models.CharField(_("content type"), max_length=100)
    description = models.CharField(_("description"), max_length=200, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("report photo")
        verbose_name_plural = _("report photos")
        ordering = ["kind", "id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        storage, path = self.file.storage, self.file.name
        result = super().delete(*args, **kwargs)
        transaction.on_commit(lambda: storage.delete(path))
        return result


class BlockType(models.TextChoices):
    CLOUD_ACCOUNT = "cloud_account", _("Cloud Account")
    MDM = "mdm", _("MDM")
    BIOS_PASSWORD = "bios_password", _("BIOS Password")
    FACTORY_RESET = "factory_reset", _("Factory Reset Protection")
    OTHER = "other", _("Other")


class FindingStatus(models.TextChoices):
    SUGGESTED = "suggested", _("Suggested")
    APPROVED = "approved", _("Approved")
    DISPUTED = "disputed", _("Disputed")
    CHARGEABLE = "chargeable", _("Chargeable")
    CHARGED = "charged", _("Charged")
    CANCELLED = "cancelled", _("Cancelled")


class Finding(models.Model):
    """A problem recorded in a report that may be charged to the customer. Its value comes from
    the penalty table (asset class × kind, on the report's date); without a rate it cannot be
    approved (RN-11). Only supervisors change a value, with a justification."""

    report = models.ForeignKey(InspectionReport, on_delete=models.CASCADE, related_name="findings")
    kind = models.CharField(_("kind"), max_length=20, choices=FindingKind.choices)
    block_type = models.CharField(
        _("block type"), max_length=15, choices=BlockType.choices, blank=True
    )
    # The kit item it is about (missing items)
    item = models.CharField(_("item"), max_length=200, blank=True)
    description = models.TextField(_("description"), blank=True)
    value = models.DecimalField(_("value"), max_digits=12, decimal_places=2, null=True, blank=True)
    value_overridden = models.BooleanField(default=False)
    value_justification = models.TextField(_("value justification"), blank=True)
    status = models.CharField(
        _("status"), max_length=12, choices=FindingStatus.choices, default=FindingStatus.SUGGESTED
    )
    # Suggested by the system (missing kit items, heavy cleaning): kept in step with the report
    automatic = models.BooleanField(_("automatic"), default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("finding")
        verbose_name_plural = _("findings")
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(value__isnull=True) | models.Q(value__gte=0),
                name="finding_value_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.report})"


class ErasureResult(models.TextChoices):
    SUCCESS = "success", _("Success")
    FAILURE = "failure", _("Failure")


def _certificate_path(instance, filename: str) -> str:
    ext = posixpath.splitext(filename)[1].lower()
    return f"inventory/certificates/{instance.asset_id}/{uuid.uuid4().hex}{ext}"


class ErasureCertificate(models.Model):
    """A data erasure of one storage device of an asset, with the tool and method defined for
    its lot and class (RN-04). A failure removes the disk for physical destruction: it becomes a
    child asset in scrap (RN-13)."""

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="erasures")
    report = models.ForeignKey(
        InspectionReport, on_delete=models.PROTECT, null=True, blank=True, related_name="erasures"
    )
    disk_serial = models.CharField(_("disk serial number"), max_length=100, blank=True)
    tool = models.ForeignKey(ErasureTool, on_delete=models.PROTECT, related_name="certificates")
    tool_version = models.CharField(_("tool version"), max_length=40, blank=True)
    method = models.CharField(_("method"), max_length=15, choices=ErasureMethod.choices)
    result = models.CharField(_("result"), max_length=10, choices=ErasureResult.choices)
    removed_disk = models.ForeignKey(
        Asset, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    at = models.DateTimeField(_("date and time"), auto_now_add=True)
    file = models.FileField(_("file"), upload_to=_certificate_path, max_length=255, blank=True)
    name = models.CharField(_("name"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("erasure certificate")
        verbose_name_plural = _("erasure certificates")
        ordering = ["-at", "-id"]

    def __str__(self):
        return f"{self.asset} · {self.result}"


# --- Phase 4: deadlines, blocks, disputes, alerts ----------------------------------------------


class DeadlineKind(models.TextChoices):
    BLOCK_RELEASE = "block_release", _("Block Release")
    DISPUTE = "dispute", _("Report Dispute")
    DISPUTE_ANALYSIS = "dispute_analysis", _("Dispute Analysis")


class DeadlineSetting(models.Model):
    """How long something may take: days, counted as calendar or business days (holidays
    skipped), and how many days before the end reminders are sent."""

    kind = models.CharField(_("kind"), max_length=20, choices=DeadlineKind.choices, unique=True)
    days = models.PositiveSmallIntegerField(_("days"))
    business_days = models.BooleanField(_("business days"), default=False)
    reminder_days = ArrayField(
        models.PositiveSmallIntegerField(), default=list, blank=True, verbose_name=_("reminders")
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("deadline")
        verbose_name_plural = _("deadlines")
        ordering = ["kind"]

    def __str__(self):
        return self.kind

    @classmethod
    def of(cls, kind: str) -> "DeadlineSetting":
        defaults = DEFAULT_DEADLINES[kind]
        setting, _created = cls.objects.get_or_create(kind=kind, defaults=defaults)
        return setting


# Proposed with Fernando (editable): block release 15 calendar days; dispute 10 business days;
# analysis 5 business days; reminders 3 and 1 day before
DEFAULT_DEADLINES = {
    DeadlineKind.BLOCK_RELEASE: {"days": 15, "business_days": False, "reminder_days": [3, 1]},
    DeadlineKind.DISPUTE: {"days": 10, "business_days": True, "reminder_days": [3, 1]},
    DeadlineKind.DISPUTE_ANALYSIS: {"days": 5, "business_days": True, "reminder_days": [1]},
}


class Holiday(models.Model):
    """A day not counted as a business day."""

    date = models.DateField(_("date"), unique=True)
    name = models.CharField(_("name"), max_length=100)

    class Meta:
        verbose_name = _("holiday")
        verbose_name_plural = _("holidays")
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} {self.name}"


class AgingLimit(models.Model):
    """How many days an asset may stay in a status before an alert (empty: no alert)."""

    status = models.CharField(_("status"), max_length=20, choices=AssetStatus.choices, unique=True)
    days = models.PositiveSmallIntegerField(_("days"), null=True, blank=True)

    class Meta:
        verbose_name = _("aging limit")
        verbose_name_plural = _("aging limits")
        ordering = ["status"]

    def __str__(self):
        return self.status


class BlockStatus(models.TextChoices):
    OPEN = "open", _("Open")
    RELEASE_REPORTED = "release_reported", _("Release Reported")
    RELEASED = "released", _("Released")
    EXPIRED = "expired", _("Expired")
    CLOSED = "closed", _("Closed")


class ExpiredDecision(models.TextChoices):
    PARTS = "parts", _("Parts")
    SCRAP = "scrap", _("Scrap")
    OTHER = "other", _("Other")


class BlockFollowUp(models.Model):
    """The customer must release an access block (cloud account, MDM, BIOS password…) by a
    deadline counted from the notification. Released → the asset goes back to inspection;
    expired → the finding becomes chargeable and a supervisor decides the asset's destination
    (RN-20)."""

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="block_followups")
    finding = models.OneToOneField(Finding, on_delete=models.PROTECT, related_name="followup")
    block_type = models.CharField(_("block type"), max_length=15, choices=BlockType.choices)
    status = models.CharField(
        _("status"), max_length=20, choices=BlockStatus.choices, default=BlockStatus.OPEN
    )
    notified_at = models.DateTimeField(_("notified at"), null=True, blank=True)
    due_date = models.DateField(_("due date"), null=True, blank=True)
    release_reported_at = models.DateTimeField(_("release reported at"), null=True, blank=True)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    checked_at = models.DateTimeField(_("checked at"), null=True, blank=True)
    decision = models.CharField(
        _("decision"), max_length=10, choices=ExpiredDecision.choices, blank=True
    )
    decision_notes = models.TextField(_("decision notes"), blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(_("decided at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("block follow-up")
        verbose_name_plural = _("block follow-ups")
        ordering = ["due_date", "id"]

    def __str__(self):
        return f"{self.asset} · {self.block_type}"


class DisputeStatus(models.TextChoices):
    OPEN = "open", _("Open")
    IN_ANALYSIS = "in_analysis", _("In Analysis")
    DECIDED = "decided", _("Decided")
    ESCALATED = "escalated", _("Escalated")


class DisputeDecision(models.TextChoices):
    UPHELD = "upheld", _("Upheld")
    PARTIALLY_UPHELD = "partially_upheld", _("Partially Upheld")
    REJECTED = "rejected", _("Rejected")


class Dispute(models.Model):
    """A customer disputes findings of a report sent to them, within the dispute deadline
    (RN-21). The asset is held until a decision by someone other than the report's technician
    (RN-14): upheld (all or part) → a new report version with the findings cancelled; rejected
    → the findings are chargeable."""

    report = models.ForeignKey(InspectionReport, on_delete=models.PROTECT, related_name="disputes")
    findings = models.ManyToManyField(Finding, related_name="disputes")
    justification = models.TextField(_("justification"))
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    registered_at = models.DateTimeField(_("registered at"), auto_now_add=True)
    analysis_due = models.DateField(_("analysis due date"))
    analyst = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reinspected = models.BooleanField(_("reinspected"), default=False)
    status = models.CharField(
        _("status"), max_length=12, choices=DisputeStatus.choices, default=DisputeStatus.OPEN
    )
    decision = models.CharField(
        _("decision"), max_length=20, choices=DisputeDecision.choices, blank=True
    )
    decision_notes = models.TextField(_("decision notes"), blank=True)
    new_report = models.ForeignKey(
        InspectionReport, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(_("decided at"), null=True, blank=True)

    class Meta:
        verbose_name = _("dispute")
        verbose_name_plural = _("disputes")
        ordering = ["-registered_at", "-id"]

    def __str__(self):
        return f"{self.report} · {self.status}"


def _evidence_path(instance, filename: str) -> str:
    ext = posixpath.splitext(filename)[1].lower()
    return f"inventory/evidence/{uuid.uuid4().hex}{ext}"


class Evidence(models.Model):
    """A file attached to a block follow-up or a dispute."""

    followup = models.ForeignKey(
        BlockFollowUp, on_delete=models.CASCADE, null=True, blank=True, related_name="evidence"
    )
    dispute = models.ForeignKey(
        Dispute, on_delete=models.CASCADE, null=True, blank=True, related_name="evidence"
    )
    file = models.FileField(_("file"), upload_to=_evidence_path, max_length=255)
    name = models.CharField(_("name"), max_length=255)
    size = models.PositiveBigIntegerField(_("size (bytes)"))
    content_type = models.CharField(_("content type"), max_length=100)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("evidence")
        verbose_name_plural = _("evidence")
        ordering = ["uploaded_at", "id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        storage, path = self.file.storage, self.file.name
        result = super().delete(*args, **kwargs)
        transaction.on_commit(lambda: storage.delete(path))
        return result


class AlertSeverity(models.TextChoices):
    """What a notification is: it decides its icon and color."""

    INFO = "info", _("Information")  # an event happened (no error, nothing to fix)
    WARNING = "warning", _("Warning")  # an event that calls for attention
    ERROR = "error", _("Error")  # something went wrong
    SUCCESS = "success", _("Completion")  # a task or process finished well


class AlertScope(models.TextChoices):
    """Whom it concerns: the user (their work, their roles) or everyone (the system)."""

    USER = "user", _("User")
    SYSTEM = "system", _("System")


class Alert(models.Model):
    """A notification: something one user must look at (a deadline near or past, an asset aging
    in a status…). Always one user's — an event for a role becomes one alert per user with it
    (`followups.alert`). Created by the daily routine, once per event and user (`key`)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alerts"
    )
    kind = models.CharField(_("kind"), max_length=30)
    severity = models.CharField(
        _("severity"), max_length=10, choices=AlertSeverity, default=AlertSeverity.INFO
    )
    # System (global): every active user got their own copy
    scope = models.CharField(_("scope"), max_length=10, choices=AlertScope, default=AlertScope.USER)
    # Values the message shows ({"asset": "H…", "days": 3, …}); the text is translated by the UI
    params = models.JSONField(default=dict, blank=True)
    # What it is about: "block:12", "dispute:3", "asset:40"…
    ref = models.CharField(max_length=40, blank=True)
    # The event (the same for every user it reached)
    key = models.CharField(max_length=120)
    read_at = models.DateTimeField(_("read at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("alert")
        verbose_name_plural = _("alerts")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "key"], name="inventory_alert_once_per_user")
        ]

    def __str__(self):
        return self.key


# --- Phase 5: disposals ---------------------------------------------------------------------


class DisposalKind(models.TextChoices):
    RELOCATION = "relocation", _("Relocation")
    LESSEE_SALE = "lessee_sale", _("Sale to the Lessee")
    THIRD_PARTY_SALE = "third_party_sale", _("Sale to Third Parties")
    DISCARD = "discard", _("Discard")
    # Recorded by taking a scrap asset apart (never created by hand)
    PARTS = "parts", _("Parts")


# Kinds whose destination is a customer (relocation and lessee sale: a lessee; third-party
# sale: the buyer, registered as a customer — decision)
CUSTOMER_KINDS = (DisposalKind.RELOCATION, DisposalKind.LESSEE_SALE, DisposalKind.THIRD_PARTY_SALE)


class DisposalStatus(models.TextChoices):
    RESERVED = "reserved", _("Reserved")
    PICKING = "picking", _("Picking")
    SHIPPED = "shipped", _("Shipped")
    CANCELLED = "cancelled", _("Cancelled")


OPEN_DISPOSAL = (DisposalStatus.RESERVED, DisposalStatus.PICKING)


class Disposal(models.Model):
    """The way out of the stock: a relocation to another lessee, a sale (to the lessee or to a
    buyer), a discard, or the parts of a scrap asset taken apart. Assets are reserved, picked by
    reading each ID against the list (to a shipping area) and shipped — written off. Only
    inventory.disposals changes it."""

    year = models.PositiveSmallIntegerField(_("year"))
    sequence = models.PositiveIntegerField(_("sequence"))
    kind = models.CharField(_("kind"), max_length=20, choices=DisposalKind.choices)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=DisposalStatus.choices,
        default=DisposalStatus.RESERVED,
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="disposals", verbose_name=_("warehouse")
    )
    # Relocation / lessee sale: the lessee; third-party sale: the buyer
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disposals",
        verbose_name=_("customer"),
    )
    # Relocation: the contract the assets go to (contracts live outside Horizon)
    contract = models.CharField(_("contract"), max_length=60, blank=True)
    # Discard: the provider that destroys or recycles them
    discard_provider = models.ForeignKey(
        "service_providers.ServiceProvider",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disposals",
        verbose_name=_("discard provider"),
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disposals",
        verbose_name=_("shipping appointment"),
    )
    document_number = models.CharField(_("document number"), max_length=60, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    keywords = keywords_field()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    shipped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    shipped_at = models.DateTimeField(_("shipped at"), null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)
    cancel_reason = models.CharField(_("reason for cancelling"), max_length=300, blank=True)

    class Meta:
        verbose_name = _("disposal")
        verbose_name_plural = _("disposals")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["year", "sequence"], name="disposal_unique_code"),
        ]

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        return yearly_code("DSP", self.year, self.sequence)

    @property
    def ref(self) -> str:
        """The movement events' `document_ref`."""
        return f"disposal:{self.pk}"


class DisposalItem(models.Model):
    """One line of a disposal: an asset, or a quantity of an accessory model (condition good,
    or scrap in discards), with its value per unit (sales and relocations — decision)."""

    disposal = models.ForeignKey(Disposal, on_delete=models.CASCADE, related_name="items")
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disposal_items",
        verbose_name=_("asset"),
    )
    accessory_model = models.ForeignKey(
        "catalogs.AssetModel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("accessory model"),
    )
    quantity = models.PositiveIntegerField(_("quantity"), default=1)
    condition = models.CharField(
        _("condition"),
        max_length=10,
        choices=AccessoryCondition.choices,
        default=AccessoryCondition.GOOD,
    )
    unit_value = models.DecimalField(
        _("unit value"), max_digits=14, decimal_places=2, null=True, blank=True
    )
    # Picking: units read (assets: 0 or 1; accessories: up to the quantity)
    picked_quantity = models.PositiveIntegerField(_("picked quantity"), default=0)
    picked_at = models.DateTimeField(_("picked at"), null=True, blank=True)
    picked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = _("disposal item")
        verbose_name_plural = _("disposal items")
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(asset__isnull=False, accessory_model__isnull=True, quantity=1)
                | models.Q(asset__isnull=True, accessory_model__isnull=False, quantity__gt=0),
                name="disposal_item_asset_or_accessory",
            ),
            models.CheckConstraint(
                condition=models.Q(picked_quantity__lte=models.F("quantity")),
                name="disposal_item_picked_at_most_quantity",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_value__isnull=True) | models.Q(unit_value__gte=0),
                name="disposal_item_value_not_negative",
            ),
        ]

    def __str__(self):
        return str(self.asset or f"{self.accessory_model} × {self.quantity}")

    @property
    def picked(self) -> bool:
        return self.picked_quantity >= self.quantity


class DisposalFileKind(models.TextChoices):
    DOCUMENT = "document", _("Shipping Document")
    CERTIFICATE = "certificate", _("Destination Certificate")
    OTHER = "other", _("Other")


def _disposal_file_path(instance, filename: str) -> str:
    ext = posixpath.splitext(filename)[1].lower()
    return f"inventory/disposals/{uuid.uuid4().hex}{ext}"


class DisposalFile(models.Model):
    """The shipping document (invoice…), the destination certificate of a discard (RN-23) or
    another file of a disposal."""

    disposal = models.ForeignKey(Disposal, on_delete=models.CASCADE, related_name="files")
    kind = models.CharField(_("kind"), max_length=12, choices=DisposalFileKind.choices)
    file = models.FileField(_("file"), upload_to=_disposal_file_path, max_length=255)
    name = models.CharField(_("name"), max_length=255)
    size = models.PositiveBigIntegerField(_("size (bytes)"))
    content_type = models.CharField(_("content type"), max_length=100)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("disposal file")
        verbose_name_plural = _("disposal files")
        ordering = ["uploaded_at", "id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        storage, path = self.file.storage, self.file.name
        result = super().delete(*args, **kwargs)
        transaction.on_commit(lambda: storage.delete(path))
        return result


# --- Phase 6: transfers between warehouses ---------------------------------------------------


class TransferStatus(models.TextChoices):
    REQUESTED = "requested", _("Requested")
    APPROVED = "approved", _("Approved")
    PICKING = "picking", _("Picking")
    IN_TRANSIT = "in_transit", _("In Transit")
    RECEIVED = "received", _("Received")
    RECEIVED_WITH_DISCREPANCY = "received_with_discrepancy", _("Received with Discrepancy")
    CANCELLED = "cancelled", _("Cancelled")


# Before sending: items may still change (requested) or be picked
BEFORE_SENDING = (TransferStatus.REQUESTED, TransferStatus.APPROVED, TransferStatus.PICKING)
# Holding its assets (they go nowhere else meanwhile)
OPEN_TRANSFER = (*BEFORE_SENDING, TransferStatus.IN_TRANSIT)

# Statuses an asset may travel in (decision): never in triage, in inspection or reserved
TRANSFERABLE = (
    AssetStatus.AVAILABLE,
    AssetStatus.SCRAP,
    AssetStatus.BLOCKED,
    AssetStatus.AWAITING_INSPECTION,
)


class Transfer(models.Model):
    """Assets (and accessories) sent from one warehouse to another: requested, approved by a
    supervisor, picked by reading each ID against the list (RN-24), sent with the fiscal
    document (in transit at the virtual location), received at the destination by reading
    each ID (back to the status they had — RN-02 applies there). Only inventory.transfers
    changes it."""

    year = models.PositiveSmallIntegerField(_("year"))
    sequence = models.PositiveIntegerField(_("sequence"))
    origin = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="transfers_out", verbose_name=_("origin")
    )
    destination = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="transfers_in",
        verbose_name=_("destination"),
    )
    reason = models.TextField(_("reason"))
    status = models.CharField(
        _("status"),
        max_length=30,
        choices=TransferStatus.choices,
        default=TransferStatus.REQUESTED,
    )
    fiscal_document_number = models.CharField(
        _("fiscal document number"), max_length=60, blank=True
    )
    # Days it may take on the road; later → an alert (RN-25)
    transit_days = models.PositiveSmallIntegerField(_("transit days"), default=5)
    notes = models.TextField(_("notes"), blank=True)
    keywords = keywords_field()
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    requested_at = models.DateTimeField(_("requested at"), auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    received_at = models.DateTimeField(_("received at"), null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)
    cancel_reason = models.CharField(_("reason for cancelling"), max_length=300, blank=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("transfer")
        verbose_name_plural = _("transfers")
        ordering = ["-requested_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["year", "sequence"], name="transfer_unique_code"),
            models.CheckConstraint(
                condition=~models.Q(origin=models.F("destination")),
                name="transfer_between_two_warehouses",
            ),
        ]

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        return yearly_code("TRF", self.year, self.sequence)

    @property
    def ref(self) -> str:
        """The movement events' `document_ref`."""
        return f"transfer:{self.pk}"


class TransferItem(models.Model):
    """An asset (with the status it travels in) or a quantity of an accessory model; checked at
    the origin (picked) and at the destination (received)."""

    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="items")
    asset = models.ForeignKey(
        Asset, on_delete=models.PROTECT, null=True, blank=True, related_name="transfer_items"
    )
    accessory_model = models.ForeignKey(
        "catalogs.AssetModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    quantity = models.PositiveIntegerField(_("quantity"), default=1)
    condition = models.CharField(
        _("condition"),
        max_length=10,
        choices=AccessoryCondition.choices,
        default=AccessoryCondition.GOOD,
    )
    # The status the asset had when it left (it comes back to it at the destination)
    status_before = models.CharField(max_length=20, choices=AssetStatus.choices, blank=True)
    # The container it travels in, when it was read with it
    container = models.ForeignKey(
        Container, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    picked_quantity = models.PositiveIntegerField(_("picked quantity"), default=0)
    picked_at = models.DateTimeField(_("picked at"), null=True, blank=True)
    picked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    received_quantity = models.PositiveIntegerField(_("received quantity"), default=0)
    received_at = models.DateTimeField(_("received at"), null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    received_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = _("transfer item")
        verbose_name_plural = _("transfer items")
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(asset__isnull=False, accessory_model__isnull=True, quantity=1)
                | models.Q(asset__isnull=True, accessory_model__isnull=False, quantity__gt=0),
                name="transfer_item_asset_or_accessory",
            ),
            models.CheckConstraint(
                condition=models.Q(picked_quantity__lte=models.F("quantity"))
                & models.Q(received_quantity__lte=models.F("picked_quantity")),
                name="transfer_item_quantities",
            ),
        ]

    def __str__(self):
        return str(self.asset or f"{self.accessory_model} × {self.quantity}")

    @property
    def picked(self) -> bool:
        return self.picked_quantity >= self.quantity

    @property
    def received(self) -> bool:
        return self.received_quantity >= self.quantity


class TransferFileKind(models.TextChoices):
    FISCAL_DOCUMENT = "fiscal_document", _("Fiscal Document")
    OTHER = "other", _("Other")


def _transfer_file_path(instance, filename: str) -> str:
    ext = posixpath.splitext(filename)[1].lower()
    return f"inventory/transfers/{uuid.uuid4().hex}{ext}"


class TransferFile(models.Model):
    """The fiscal document of a transfer (required to send it) or another file."""

    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="files")
    kind = models.CharField(_("kind"), max_length=20, choices=TransferFileKind.choices)
    file = models.FileField(_("file"), upload_to=_transfer_file_path, max_length=255)
    name = models.CharField(_("name"), max_length=255)
    size = models.PositiveBigIntegerField(_("size (bytes)"))
    content_type = models.CharField(_("content type"), max_length=100)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("transfer file")
        verbose_name_plural = _("transfer files")
        ordering = ["uploaded_at", "id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        storage, path = self.file.storage, self.file.name
        result = super().delete(*args, **kwargs)
        transaction.on_commit(lambda: storage.delete(path))
        return result


# --- Phase 7: inventory counts ---------------------------------------------------------------


class CountKind(models.TextChoices):
    CYCLIC = "cyclic", _("Cyclic")
    GENERAL = "general", _("General")


class CountStatus(models.TextChoices):
    COUNTING = "counting", _("Counting")
    # Closed: divergences found, adjustments waiting for a supervisor
    CLOSED = "closed", _("Closed")
    FINISHED = "finished", _("Finished")
    CANCELLED = "cancelled", _("Cancelled")


class InventoryCount(models.Model):
    """Counting what is physically at some locations of a warehouse (cyclic) or at all of them
    (general). Blind: the counters read IDs and quantities without seeing what is expected.
    While counting, nothing moves in or out of its locations. Closing finds the divergences;
    each becomes an adjustment a supervisor other than the counters approves (RN-26). Only
    inventory.counting changes it."""

    year = models.PositiveSmallIntegerField(_("year"))
    sequence = models.PositiveIntegerField(_("sequence"))
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="counts", verbose_name=_("warehouse")
    )
    kind = models.CharField(_("kind"), max_length=10, choices=CountKind.choices)
    # The scope: the chosen locations and everything under them (all, in a general count)
    locations = models.ManyToManyField(Location, related_name="counts", verbose_name=_("locations"))
    status = models.CharField(
        _("status"), max_length=10, choices=CountStatus.choices, default=CountStatus.COUNTING
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    notes = models.TextField(_("notes"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)
    cancel_reason = models.CharField(_("reason for cancelling"), max_length=300, blank=True)
    # Expected assets and matches found when closing (for the location accuracy indicator)
    expected_assets = models.PositiveIntegerField(_("expected assets"), default=0)
    matched_assets = models.PositiveIntegerField(_("assets found where expected"), default=0)

    class Meta:
        verbose_name = _("inventory count")
        verbose_name_plural = _("inventory counts")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["year", "sequence"], name="count_unique_code"),
        ]

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        return yearly_code("INV", self.year, self.sequence)

    @property
    def ref(self) -> str:
        return f"count:{self.pk}"


class CountReading(models.Model):
    """What a counter read at a location: an asset's ID, or a quantity of an accessory model
    (at the location or in a container there)."""

    count = models.ForeignKey(InventoryCount, on_delete=models.CASCADE, related_name="readings")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="+")
    asset = models.ForeignKey(
        Asset, on_delete=models.PROTECT, null=True, blank=True, related_name="count_readings"
    )
    accessory_model = models.ForeignKey(
        "catalogs.AssetModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    container = models.ForeignKey(
        Container, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    quantity = models.PositiveIntegerField(_("quantity"), default=1)
    condition = models.CharField(
        _("condition"),
        max_length=10,
        choices=AccessoryCondition.choices,
        default=AccessoryCondition.GOOD,
    )
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    counted_at = models.DateTimeField(_("counted at"), auto_now_add=True)

    class Meta:
        verbose_name = _("count reading")
        verbose_name_plural = _("count readings")
        ordering = ["counted_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(asset__isnull=False, accessory_model__isnull=True)
                | models.Q(asset__isnull=True, accessory_model__isnull=False),
                name="reading_asset_or_accessory",
            ),
            models.UniqueConstraint(
                fields=["count", "asset"],
                condition=models.Q(asset__isnull=False),
                name="reading_asset_once_per_count",
            ),
        ]

    def __str__(self):
        return str(self.asset or f"{self.accessory_model} × {self.quantity}")


class DivergenceKind(models.TextChoices):
    NOT_FOUND = "not_found", _("Not Found")
    OTHER_LOCATION = "other_location", _("Found at Another Location")
    UNEXPECTED = "unexpected", _("Not Expected Here")
    BALANCE = "balance", _("Balance Difference")


class AdjustmentStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")


class CountDivergence(models.Model):
    """A difference found when a count closes, and the adjustment it proposes: an asset not
    found (written off as lost), found at another location or not expected here (moved to where
    it was found), an accessory balance different from the count (set to it). Applied only
    when a supervisor other than the counters approves it (RN-26), as INVENTORY_ADJUSTMENT
    events."""

    count = models.ForeignKey(InventoryCount, on_delete=models.CASCADE, related_name="divergences")
    kind = models.CharField(_("kind"), max_length=20, choices=DivergenceKind.choices)
    asset = models.ForeignKey(
        Asset, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    accessory_model = models.ForeignKey(
        "catalogs.AssetModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    condition = models.CharField(max_length=10, choices=AccessoryCondition.choices, blank=True)
    container = models.ForeignKey(
        Container, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Where the records say it is / where it was counted
    expected_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    found_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    expected_quantity = models.IntegerField(_("expected quantity"), null=True, blank=True)
    counted_quantity = models.IntegerField(_("counted quantity"), null=True, blank=True)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=AdjustmentStatus.choices,
        default=AdjustmentStatus.PENDING,
    )
    reason = models.TextField(_("reason"), blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(_("decided at"), null=True, blank=True)

    class Meta:
        verbose_name = _("count divergence")
        verbose_name_plural = _("count divergences")
        ordering = ["kind", "id"]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.count})"
