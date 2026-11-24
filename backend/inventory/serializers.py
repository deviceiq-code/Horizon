import re

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from catalogs.models import Vertical
from config.keywords import KeywordsField
from config.parties import AddressFieldsMixin, collapse_spaces
from customers.models import Customer
from service_providers.models import ServiceKind
from users.display import display_name_in

from .codes import ASSET_PREFIX, format_code
from .grades import periods_overlap
from .models import (
    GRADE_CODES,
    AccessoryBalance,
    AgingLimit,
    Alert,
    Appointment,
    AppointmentKind,
    AppointmentStatus,
    Asset,
    BlockFollowUp,
    Container,
    CountDivergence,
    CountReading,
    DeadlineSetting,
    Disposal,
    DisposalFile,
    DisposalItem,
    Dispute,
    ErasureCertificate,
    ErasureMethod,
    ErasureTool,
    Evidence,
    ExpectedItem,
    Finding,
    FindingKind,
    GradeDomain,
    GradeLevel,
    Holiday,
    InspectionReport,
    InventoryCount,
    LabelRange,
    Location,
    LotAttachment,
    LotErasureTool,
    LotStatus,
    MovementEvent,
    Occurrence,
    OccurrenceStatus,
    Ownership,
    PenaltyRate,
    ReceivingLot,
    ReportPhoto,
    ReportStatus,
    Transfer,
    TransferFile,
    TransferItem,
    Warehouse,
)
from .states import AreaType, accepted_statuses


class WarehouseSerializer(AddressFieldsMixin, serializers.ModelSerializer):
    # Read: who runs an outsourced warehouse ({id, name} — trade name when it has one)
    service_provider_detail = serializers.SerializerMethodField()
    # Write: ids (at least one; only enabled verticals can be added). Read: also names
    verticals = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Vertical.objects.all(), required=False
    )
    verticals_detail = serializers.SerializerMethodField()
    keywords = KeywordsField()

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "name",
            "code",
            "ownership",
            "service_provider",
            "service_provider_detail",
            "verticals",
            "verticals_detail",
            "contact_name",
            "email",
            "phone",
            "country",
            "postal_code",
            "street",
            "number",
            "complement",
            "district",
            "city",
            "state",
            "is_active",
            "notes",
            "keywords",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at"]
        # The name's uniqueness is checked in validate_name with a friendlier message
        validators = []

    def get_service_provider_detail(self, obj) -> dict | None:
        provider = obj.service_provider
        return {"id": provider.id, "name": str(provider)} if provider else None

    def get_verticals_detail(self, obj) -> list[dict]:
        refs = [
            {"id": v.id, "name": v.name, "is_enabled": v.is_enabled} for v in obj.verticals.all()
        ]
        return sorted(refs, key=lambda ref: ref["name"].lower())

    def validate_verticals(self, value):
        if not value:
            raise serializers.ValidationError(_("Choose at least one business vertical."))
        kept = set(self.instance.verticals.all()) if self.instance is not None else set()
        if any(not v.is_enabled and v not in kept for v in value):
            raise serializers.ValidationError(_("Disabled verticals cannot be added."))
        return list(dict.fromkeys(value))

    def validate_name(self, value):
        value = collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        duplicates = Warehouse.objects.filter(name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(_("A warehouse with this name already exists."))
        return value

    def validate(self, attrs):
        errors = self.address_errors(attrs)
        if self.instance is None and "verticals" not in attrs:
            errors["verticals"] = _("Choose at least one business vertical.")

        ownership = self.current(attrs, "ownership", Ownership.OWN)
        if ownership == Ownership.OWN:
            # Own warehouses have no provider (dropped when switching from outsourced)
            attrs["service_provider"] = None
        else:
            provider = self.current(attrs, "service_provider", None)
            if provider is None:
                errors["service_provider"] = _(
                    "Choose the service provider that runs this warehouse."
                )
            elif provider != getattr(self.instance, "service_provider", None):
                # Checked when chosen: a provider deactivated later does not block editing
                if not provider.provides(ServiceKind.WAREHOUSING):
                    errors["service_provider"] = _("This provider does not offer warehousing.")
                elif not provider.is_active:
                    errors["service_provider"] = _("This service provider is inactive.")

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        verticals = validated_data.pop("verticals", [])
        warehouse = super().create(validated_data)
        warehouse.verticals.set(verticals)
        return warehouse

    def update(self, instance, validated_data):
        verticals = validated_data.pop("verticals", None)
        warehouse = super().update(instance, validated_data)
        if verticals is not None:
            warehouse.verticals.set(verticals)
        return warehouse


# --- Foundation: locations, containers, assets, events, labels -------------------------------


_SEGMENT = re.compile(r"^[A-Z0-9]{1,20}$")


def location_ref(location) -> dict | None:
    if location is None:
        return None
    return {"id": location.id, "code": location.code, "area_type": location.area_type}


class LocationSerializer(serializers.ModelSerializer):
    """A location's warehouse, parent and segment are set on creation and never change (its
    code is printed on labels); the area type, description and active flag can."""

    accepted_statuses = serializers.SerializerMethodField()
    children_count = serializers.IntegerField(read_only=True, default=0)
    assets_count = serializers.IntegerField(read_only=True, default=0)
    containers_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Location
        fields = [
            "id",
            "warehouse",
            "parent",
            "segment",
            "code",
            "area_type",
            "accepted_statuses",
            "description",
            "is_active",
            "children_count",
            "assets_count",
            "containers_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at"]
        extra_kwargs = {
            "warehouse": {"required": False},
            "area_type": {"required": False},
            "parent": {"required": False},
        }

    def get_accepted_statuses(self, obj) -> list[str]:
        return accepted_statuses(obj.area_type)

    def validate_segment(self, value):
        value = "".join((value or "").split()).upper()
        if not _SEGMENT.match(value):
            raise serializers.ValidationError(
                _("Use 1 to 20 letters and digits, without spaces or symbols.")
            )
        return value

    def validate_area_type(self, value):
        if value == AreaType.VIRTUAL_TRANSIT:
            raise serializers.ValidationError(_("Only the system has a virtual location."))
        return value

    def validate(self, attrs):
        errors = {}
        if self.instance is None:
            parent = attrs.get("parent")
            warehouse = attrs.get("warehouse")
            if parent is not None:
                if parent.is_virtual:
                    errors["parent"] = _("The virtual location has no sub-locations.")
                elif warehouse is not None and warehouse != parent.warehouse:
                    errors["parent"] = _("The parent location is in another warehouse.")
                warehouse = parent.warehouse
                attrs["warehouse"] = warehouse
                attrs.setdefault("area_type", parent.area_type)
            if warehouse is None:
                errors["warehouse"] = _("This field is required.")
            elif "segment" in attrs:
                base = parent.code if parent is not None else warehouse.code
                attrs["code"] = f"{base}-{attrs['segment']}"
                if Location.objects.filter(code=attrs["code"]).exists():
                    errors["segment"] = _("There is already a location with this code.")
            if "area_type" not in attrs:
                errors["area_type"] = _("This field is required.")
        else:
            # Where it is and its code never change
            for field in ("warehouse", "parent", "segment"):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    errors[field] = _("This cannot be changed: the code is on the labels.")
            if self.instance.is_virtual:
                errors["area_type"] = _("The virtual location cannot be changed.")
            elif "area_type" in attrs and attrs["area_type"] != self.instance.area_type:
                incompatible = [
                    a.horizon_id
                    for a in self.instance.assets.all()
                    if a.status not in accepted_statuses(attrs["area_type"])
                    and not (attrs["area_type"] == AreaType.QUARANTINE and a.held_for_dispute)
                ]
                if incompatible:
                    errors["area_type"] = _(
                        "Assets here would not fit the new area type: %(assets)s."
                    ) % {"assets": ", ".join(incompatible[:5])}
            if attrs.get("is_active") is False and (
                self.instance.assets.exists() or self.instance.containers.exists()
            ):
                errors["is_active"] = _("Move the assets and containers out first.")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ContainerSerializer(serializers.ModelSerializer):
    """Created at a location (the API places it there with an entry event); moved only by
    movements."""

    current_location_detail = serializers.SerializerMethodField()
    assets_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Container
        fields = [
            "id",
            "code",
            "kind",
            "current_location",
            "current_location_detail",
            "description",
            "is_active",
            "assets_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at"]

    def get_current_location_detail(self, obj) -> dict | None:
        return location_ref(obj.current_location)

    def validate(self, attrs):
        if self.instance is not None:
            if (
                "current_location" in attrs
                and attrs["current_location"] != self.instance.current_location
            ):
                raise serializers.ValidationError(
                    {"current_location": _("Containers move by reading them at the destination.")}
                )
            if attrs.get("is_active") is False and self.instance.assets.exists():
                raise serializers.ValidationError({"is_active": _("Empty the container first.")})
        return attrs


def asset_model_ref(model) -> dict:
    return {
        "id": model.id,
        "name": model.name,
        "manufacturer_name": model.manufacturer.name,
        "asset_class": model.asset_class_id,
        "asset_class_name": model.asset_class.name,
        "asset_class_icon": model.asset_class.icon,
        "tracking": model.tracking,
        "has_storage": model.has_storage,
    }


class AssetSerializer(serializers.ModelSerializer):
    """Read: the asset with its model and place. Write (PATCH): only notes and other IDs —
    status and place change only through movements (RN-07)."""

    asset_model_detail = serializers.SerializerMethodField()
    current_location_detail = serializers.SerializerMethodField()
    current_container_detail = serializers.SerializerMethodField()
    warehouse = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            "id",
            "horizon_id",
            "asset_model",
            "asset_model_detail",
            "specs",
            "serial",
            "serial_status",
            "no_serial_reason",
            "other_ids",
            "status",
            "warehouse",
            "current_location",
            "current_location_detail",
            "current_container",
            "current_container_detail",
            "held_for_dispute",
            "condition_grade",
            "parent_asset",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [f for f in fields if f not in ("notes", "other_ids")]

    def get_asset_model_detail(self, obj) -> dict:
        return asset_model_ref(obj.asset_model)

    def get_current_location_detail(self, obj) -> dict | None:
        return location_ref(obj.current_location)

    def get_current_container_detail(self, obj) -> dict | None:
        container = obj.current_container
        return {"id": container.id, "code": container.code} if container else None

    def get_warehouse(self, obj) -> dict | None:
        warehouse = obj.current_location.warehouse
        return (
            {"id": warehouse.id, "code": warehouse.code, "name": warehouse.name}
            if warehouse
            else None
        )

    def validate_other_ids(self, value):
        allowed = {"imei", "imei2", "mac", "service_tag"}
        if not isinstance(value, dict) or not set(value) <= allowed:
            raise serializers.ValidationError(
                _("Other identifiers: %(keys)s.") % {"keys": ", ".join(sorted(allowed))}
            )
        return {key: " ".join(str(v).split()).upper() for key, v in value.items() if str(v).strip()}


class MovementEventSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source="asset.horizon_id", read_only=True, default=None)
    container_code = serializers.CharField(source="container.code", read_only=True, default=None)
    from_location_code = serializers.CharField(
        source="from_location.code", read_only=True, default=None
    )
    to_location_code = serializers.CharField(
        source="to_location.code", read_only=True, default=None
    )
    from_container_code = serializers.CharField(
        source="from_container.code", read_only=True, default=None
    )
    to_container_code = serializers.CharField(
        source="to_container.code", read_only=True, default=None
    )
    user_name = serializers.SerializerMethodField()
    accessory_model_label = serializers.SerializerMethodField()

    class Meta:
        model = MovementEvent
        fields = [
            "id",
            "kind",
            "asset",
            "asset_code",
            "container",
            "container_code",
            "accessory_model",
            "accessory_model_label",
            "quantity",
            "accessory_condition",
            "from_location_code",
            "to_location_code",
            "from_container_code",
            "to_container_code",
            "status_before",
            "status_after",
            "user",
            "user_name",
            "at",
            "reason",
            "document_ref",
            "parent_event",
            "reverses",
        ]
        read_only_fields = fields

    def get_user_name(self, obj) -> str:
        return display_name_in(self.context, obj.user)

    def get_accessory_model_label(self, obj) -> str | None:
        model = obj.accessory_model
        return f"{model.manufacturer.name} {model.name}" if model else None


class MovementSerializer(serializers.Serializer):
    """POST /movements/: the object read (asset or container) and the destination read
    (location, or a container for an asset)."""

    object_code = serializers.CharField(max_length=80)
    destination_code = serializers.CharField(max_length=80)
    # Optional: where the object was read (RN-19)
    origin_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=300)


class LabelRangeSerializer(serializers.ModelSerializer):
    first_code = serializers.SerializerMethodField()
    last_code = serializers.SerializerMethodField()
    size = serializers.IntegerField(read_only=True)
    reserved_by_name = serializers.SerializerMethodField()
    count = serializers.IntegerField(write_only=True, min_value=1)

    class Meta:
        model = LabelRange
        fields = [
            "id",
            "first_number",
            "last_number",
            "first_code",
            "last_code",
            "size",
            "count",
            "reserved_by",
            "reserved_by_name",
            "reserved_at",
        ]
        read_only_fields = [
            "id",
            "first_number",
            "last_number",
            "reserved_by",
            "reserved_at",
        ]

    def get_first_code(self, obj) -> str:
        return format_code(ASSET_PREFIX, obj.first_number)

    def get_last_code(self, obj) -> str:
        return format_code(ASSET_PREFIX, obj.last_number)

    def get_reserved_by_name(self, obj) -> str:
        return display_name_in(self.context, obj.reserved_by)


# --- Phase 2: appointments, expected lists, lots, occurrences, balances ---------------------


def _model_label(model) -> str:
    return f"{model.manufacturer.name} {model.name}"


def _customer_name(customer) -> str | None:
    return (customer.trade_name or customer.name) if customer else None


class ExpectedItemSerializer(serializers.ModelSerializer):
    asset_model_label = serializers.SerializerMethodField()
    tracking = serializers.CharField(source="asset_model.tracking", read_only=True)

    class Meta:
        model = ExpectedItem
        fields = ["id", "asset_model", "asset_model_label", "tracking", "serial", "quantity"]
        read_only_fields = ["id"]
        extra_kwargs = {"quantity": {"min_value": 1}}

    def get_asset_model_label(self, obj) -> str:
        return _model_label(obj.asset_model)

    def validate_serial(self, value):
        return "".join((value or "").split()).upper()

    def validate(self, attrs):
        if attrs.get("serial") and attrs.get("quantity", 1) != 1:
            raise serializers.ValidationError(
                {"quantity": [_("A line with a serial number is one unit.")]}
            )
        return attrs


class AppointmentSerializer(serializers.ModelSerializer):
    """`expected_items` (receivings): read only by analysts, supervisors and commercial
    (never by the receivers who count — RN-17); sending it replaces the list."""

    code = serializers.CharField(read_only=True)
    warehouse_detail = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    carrier_detail = serializers.SerializerMethodField()
    conflicts = serializers.SerializerMethodField()
    lot = serializers.SerializerMethodField()
    expected_items = ExpectedItemSerializer(many=True, required=False)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "code",
            "kind",
            "warehouse",
            "warehouse_detail",
            "customer",
            "customer_name",
            "starts_at",
            "ends_at",
            "status",
            "carrier",
            "carrier_detail",
            "carrier_name",
            "vehicle_plate",
            "driver_name",
            "expected_volumes",
            "notes",
            "conflicts",
            "lot",
            "expected_items",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("can_see_expected"):
            data.pop("expected_items", None)
        return data

    def get_warehouse_detail(self, obj) -> dict:
        return {"id": obj.warehouse_id, "code": obj.warehouse.code, "name": obj.warehouse.name}

    def get_customer_name(self, obj) -> str | None:
        return _customer_name(obj.customer)

    def get_carrier_detail(self, obj) -> dict | None:
        return {"id": obj.carrier_id, "name": str(obj.carrier)} if obj.carrier else None

    def get_conflicts(self, obj) -> list[str]:
        from .receiving import overlapping

        return [a.code for a in overlapping(obj)]

    def get_lot(self, obj) -> dict | None:
        lot = getattr(obj, "lot", None)
        return {"id": lot.id, "code": lot.code, "status": lot.status} if lot else None

    def get_created_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.created_by)

    def validate_vehicle_plate(self, value):
        return "".join((value or "").split()).upper()

    def validate_carrier(self, value):
        if value is not None and not value.provides(ServiceKind.TRANSPORT):
            raise serializers.ValidationError(_("This provider does not offer transport."))
        return value

    def validate(self, attrs):
        def current(field):
            return attrs.get(field, getattr(self.instance, field, None))

        errors = {}
        if self.instance is not None and self.instance.status == AppointmentStatus.DONE:
            raise serializers.ValidationError({"detail": _("This appointment is done.")})
        if current("kind") == AppointmentKind.RECEIVING and current("customer") is None:
            errors["customer"] = [_("A receiving needs the customer who returns the assets.")]
        starts, ends = current("starts_at"), current("ends_at")
        if starts and ends and ends <= starts:
            errors["ends_at"] = [_("The end must be after the start.")]
        if attrs.get("expected_items") and current("kind") != AppointmentKind.RECEIVING:
            errors["expected_items"] = [_("Only receivings have an expected list.")]
        serials = [
            (item["asset_model"].id, item["serial"])
            for item in attrs.get("expected_items", [])
            if item.get("serial")
        ]
        if len(serials) != len(set(serials)):
            errors["expected_items"] = [_("A serial number is listed twice for the same model.")]
        if (
            self.instance is not None
            and "expected_items" in attrs
            and getattr(self.instance, "lot", None) is not None
            and self.instance.lot.status == LotStatus.CLOSED
        ):
            errors["expected_items"] = [_("The lot is closed: its expected list cannot change.")]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        items = validated_data.pop("expected_items", [])
        from .receiving import create_with_code

        appointment = create_with_code(Appointment, **validated_data)
        ExpectedItem.objects.bulk_create(ExpectedItem(appointment=appointment, **i) for i in items)
        return appointment

    def update(self, instance, validated_data):
        items = validated_data.pop("expected_items", None)
        appointment = super().update(instance, validated_data)
        if items is not None:
            appointment.expected_items.all().delete()
            ExpectedItem.objects.bulk_create(
                ExpectedItem(appointment=appointment, **i) for i in items
            )
        return appointment


class ReceivingLotSerializer(serializers.ModelSerializer):
    """A lot as anyone sees it: never its expected list (RN-17)."""

    code = serializers.CharField(read_only=True)
    warehouse_detail = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    appointment_detail = serializers.SerializerMethodField()
    dock_detail = serializers.SerializerMethodField()
    opened_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()
    is_scheduled = serializers.BooleanField(read_only=True)
    units_count = serializers.IntegerField(read_only=True, default=0)
    open_occurrences = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = ReceivingLot
        fields = [
            "id",
            "code",
            "warehouse",
            "warehouse_detail",
            "customer",
            "customer_name",
            "appointment",
            "appointment_detail",
            "dock",
            "dock_detail",
            "fiscal_document_number",
            "status",
            "notes",
            "is_scheduled",
            "units_count",
            "open_occurrences",
            "opened_by_name",
            "opened_at",
            "closed_by_name",
            "closed_at",
        ]
        read_only_fields = [f for f in fields if f not in ("fiscal_document_number", "notes")]

    def get_warehouse_detail(self, obj) -> dict:
        return {"id": obj.warehouse_id, "code": obj.warehouse.code, "name": obj.warehouse.name}

    def get_customer_name(self, obj) -> str | None:
        return _customer_name(obj.customer)

    def get_appointment_detail(self, obj) -> dict | None:
        a = obj.appointment
        return {"id": a.id, "code": a.code} if a else None

    def get_dock_detail(self, obj) -> dict:
        return location_ref(obj.dock)

    def get_opened_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.opened_by)

    def get_closed_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.closed_by) if obj.closed_by else None


class LotOpenSerializer(serializers.Serializer):
    """Opening a lot: from a receiving appointment, or unscheduled (warehouse + customer). The
    dock is read with the gun."""

    appointment = serializers.PrimaryKeyRelatedField(
        queryset=Appointment.objects.all(), required=False, allow_null=True
    )
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(), required=False, allow_null=True
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )
    dock_code = serializers.CharField(max_length=80)
    fiscal_document_number = serializers.CharField(
        max_length=60, required=False, allow_blank=True, default=""
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("appointment") is None and attrs.get("warehouse") is None:
            raise serializers.ValidationError({"warehouse": [_("This field is required.")]})
        return attrs


class OccurrenceSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source="asset.horizon_id", read_only=True, default=None)
    asset_model_label = serializers.SerializerMethodField()
    lot_code = serializers.SerializerMethodField()
    transfer_code = serializers.SerializerMethodField()
    count_code = serializers.SerializerMethodField()
    responsible_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()
    attachments_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Occurrence
        fields = [
            "id",
            "kind",
            "lot",
            "lot_code",
            "transfer",
            "transfer_code",
            "count",
            "count_code",
            "asset",
            "asset_code",
            "asset_model",
            "asset_model_label",
            "quantity",
            "expected_serial",
            "received_serial",
            "description",
            "responsible",
            "responsible_name",
            "due_date",
            "status",
            "resolution",
            "resolved_by_name",
            "resolved_at",
            "automatic",
            "attachments_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "resolution",
            "resolved_at",
            "automatic",
            "created_at",
            "expected_serial",
            "received_serial",
            "transfer",
            "count",
        ]
        extra_kwargs = {"lot": {"required": True, "allow_null": False}}

    def get_asset_model_label(self, obj) -> str | None:
        return _model_label(obj.asset_model) if obj.asset_model else None

    def get_lot_code(self, obj) -> str | None:
        return obj.lot.code if obj.lot else None

    def get_transfer_code(self, obj) -> str | None:
        return obj.transfer.code if obj.transfer_id else None

    def get_count_code(self, obj) -> str | None:
        return obj.count.code if obj.count_id else None

    def get_responsible_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.responsible) if obj.responsible else None

    def get_resolved_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.resolved_by) if obj.resolved_by else None

    def validate(self, attrs):
        instance = self.instance
        if instance is not None:
            if instance.status != OccurrenceStatus.OPEN:
                raise serializers.ValidationError(
                    {"detail": _("This occurrence is no longer open.")}
                )
            for field in ("lot", "kind", "asset", "asset_model"):
                if field in attrs and attrs[field] != getattr(instance, field):
                    raise serializers.ValidationError({field: [_("This cannot be changed.")]})
        lot = attrs.get("lot", getattr(instance, "lot", None))
        if lot is not None and lot.status == LotStatus.CLOSED:
            raise serializers.ValidationError({"lot": [_("This lot is closed.")]})
        asset = attrs.get("asset")
        if asset is not None and lot is not None and asset.lot_id != lot.id:
            raise serializers.ValidationError({"asset": [_("This asset is not from this lot.")]})
        return attrs


class LotAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    asset_code = serializers.CharField(source="asset.horizon_id", read_only=True, default=None)

    class Meta:
        model = LotAttachment
        fields = [
            "id",
            "kind",
            "name",
            "size",
            "content_type",
            "asset",
            "asset_code",
            "occurrence",
            "uploaded_by_name",
            "uploaded_at",
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.uploaded_by)


class AccessoryBalanceSerializer(serializers.ModelSerializer):
    asset_model_label = serializers.SerializerMethodField()
    asset_class_name = serializers.CharField(source="asset_model.asset_class.name", read_only=True)
    container_code = serializers.CharField(source="container.code", read_only=True, default=None)
    location_detail = serializers.SerializerMethodField()
    warehouse = serializers.SerializerMethodField()

    class Meta:
        model = AccessoryBalance
        fields = [
            "id",
            "asset_model",
            "asset_model_label",
            "asset_class_name",
            "container",
            "container_code",
            "location_detail",
            "warehouse",
            "condition",
            "quantity",
            "updated_at",
        ]
        read_only_fields = fields

    def get_asset_model_label(self, obj) -> str:
        return _model_label(obj.asset_model)

    def get_location_detail(self, obj) -> dict:
        return location_ref(obj.place)

    def get_warehouse(self, obj) -> dict | None:
        warehouse = obj.place.warehouse
        return (
            {"id": warehouse.id, "code": warehouse.code, "name": warehouse.name}
            if warehouse
            else None
        )


# --- Phase 3: grades, penalty table, erasure tools, inspection reports ----------------------


class GradeLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeLevel
        fields = ["id", "domain", "code", "name", "description", "order"]
        read_only_fields = ["id", "domain", "code", "order"]

    def validate_name(self, value):
        value = collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value


class PenaltyRateSerializer(serializers.ModelSerializer):
    asset_class_name = serializers.CharField(source="asset_class.name", read_only=True)

    class Meta:
        model = PenaltyRate
        fields = [
            "id",
            "asset_class",
            "asset_class_name",
            "finding_kind",
            "value",
            "valid_from",
            "valid_to",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"value": {"min_value": 0}}

    def validate(self, attrs):
        def current(field):
            return attrs.get(field, getattr(self.instance, field, None))

        start, end = current("valid_from"), current("valid_to")
        if start and end and end < start:
            raise serializers.ValidationError({"valid_to": [_("The end must be after the start.")]})
        others = PenaltyRate.objects.filter(
            asset_class=current("asset_class"), finding_kind=current("finding_kind")
        )
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        for other in others:
            if periods_overlap(start, end, other.valid_from, other.valid_to):  # RN-03
                raise serializers.ValidationError(
                    {
                        "valid_from": [
                            _("Another rate of this asset class and kind is valid in this period.")
                        ]
                    }
                )
        return attrs


class ErasureToolSerializer(serializers.ModelSerializer):
    methods = serializers.ListField(child=serializers.ChoiceField(choices=ErasureMethod.choices))
    asset_classes_detail = serializers.SerializerMethodField()

    class Meta:
        model = ErasureTool
        fields = [
            "id",
            "name",
            "version",
            "methods",
            "asset_classes",
            "asset_classes_detail",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"asset_classes": {"required": False}}
        validators = []

    def get_asset_classes_detail(self, obj) -> list[dict]:
        return [{"id": c.id, "name": c.name} for c in obj.asset_classes.all()]

    def validate_name(self, value):
        value = collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate_version(self, value):
        return collapse_spaces(value)

    def validate_methods(self, value):
        chosen = set(value)
        if not chosen:
            raise serializers.ValidationError(_("Choose at least one method."))
        return [m for m in ErasureMethod.values if m in chosen]

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", ""))
        version = attrs.get("version", getattr(self.instance, "version", ""))
        duplicates = ErasureTool.objects.filter(name__iexact=name, version__iexact=version)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                {"name": [_("This tool and version are already registered.")]}
            )
        return attrs


class LotErasureToolSerializer(serializers.ModelSerializer):
    asset_class_name = serializers.CharField(source="asset_class.name", read_only=True)
    tool_label = serializers.CharField(source="tool.__str__", read_only=True)
    defined_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LotErasureTool
        fields = [
            "asset_class",
            "asset_class_name",
            "tool",
            "tool_label",
            "method",
            "defined_by_name",
            "defined_at",
        ]

    def get_defined_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.defined_by)


class ReportPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportPhoto
        fields = ["id", "kind", "name", "size", "description", "uploaded_at"]
        read_only_fields = fields


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = [
            "id",
            "kind",
            "block_type",
            "item",
            "description",
            "value",
            "value_overridden",
            "value_justification",
            "status",
            "automatic",
        ]
        read_only_fields = [
            "id",
            "item",
            "value",
            "value_overridden",
            "value_justification",
            "status",
            "automatic",
        ]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        if self.instance is not None and self.instance.automatic and "kind" in attrs:
            raise serializers.ValidationError({"kind": [_("This cannot be changed.")]})
        if kind != FindingKind.ACCESS_BLOCK:
            attrs["block_type"] = ""
        return attrs


class ErasureCertificateSerializer(serializers.ModelSerializer):
    tool_label = serializers.CharField(source="tool.__str__", read_only=True)
    operator_name = serializers.SerializerMethodField()
    removed_disk_code = serializers.CharField(
        source="removed_disk.horizon_id", read_only=True, default=None
    )

    class Meta:
        model = ErasureCertificate
        fields = [
            "id",
            "disk_serial",
            "tool_label",
            "tool_version",
            "method",
            "result",
            "removed_disk",
            "removed_disk_code",
            "operator_name",
            "at",
            "name",
        ]
        read_only_fields = fields

    def get_operator_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.operator)


class InspectionReportListSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source="asset.horizon_id", read_only=True)
    asset_model_label = serializers.SerializerMethodField()
    asset_class_icon = serializers.CharField(
        source="asset.asset_model.asset_class.icon", read_only=True
    )
    serial = serializers.CharField(source="asset.serial", read_only=True)
    customer_name = serializers.SerializerMethodField()
    lot_code = serializers.SerializerMethodField()
    technician_name = serializers.SerializerMethodField()
    grade = serializers.CharField(read_only=True)

    class Meta:
        model = InspectionReport
        fields = [
            "id",
            "asset",
            "asset_code",
            "asset_model_label",
            "asset_class_icon",
            "serial",
            "customer_name",
            "lot_code",
            "version",
            "is_current",
            "status",
            "technician",
            "technician_name",
            "started_at",
            "finished_at",
            "grade",
            "recommended_destination",
            "approved_at",
            "sent_to_customer_at",
            "dispute_deadline",
        ]
        read_only_fields = fields

    def get_asset_model_label(self, obj) -> str:
        return _model_label(obj.asset.asset_model)

    def get_customer_name(self, obj) -> str | None:
        return _customer_name(obj.asset.customer)

    def get_lot_code(self, obj) -> str | None:
        return obj.asset.lot.code if obj.asset.lot_id else None

    def get_technician_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.technician)


class InspectionReportSerializer(InspectionReportListSerializer):
    """A report with everything the inspection needs: the asset, its model's kit checklist and
    test script, the photos required by its class, photos, findings, the asset's erasures, the
    lot's erasure tool, the system's suggestions and what still prevents submitting."""

    asset_detail = serializers.SerializerMethodField()
    kit_checklist = serializers.JSONField(source="asset.asset_model.kit_checklist", read_only=True)
    test_script = serializers.JSONField(source="asset.asset_model.test_script", read_only=True)
    has_storage = serializers.BooleanField(source="asset.asset_model.has_storage", read_only=True)
    required_photo_kinds = serializers.JSONField(
        source="asset.asset_model.asset_class.required_photo_kinds", read_only=True
    )
    photos = ReportPhotoSerializer(many=True, read_only=True)
    findings = FindingSerializer(many=True, read_only=True)
    erasures = serializers.SerializerMethodField()
    lot_tool = serializers.SerializerMethodField()
    suggestions = serializers.SerializerMethodField()
    problems = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta(InspectionReportListSerializer.Meta):
        fields = InspectionReportListSerializer.Meta.fields + [
            "asset_detail",
            "conservation",
            "functioning",
            "completeness",
            "failed_components",
            "irreparable",
            "missing_items",
            "checklist_done",
            "test_results",
            "cleaning",
            "notes",
            "review_notes",
            "approved_by_name",
            "new_version_reason",
            "kit_checklist",
            "test_script",
            "has_storage",
            "required_photo_kinds",
            "photos",
            "findings",
            "erasures",
            "lot_tool",
            "suggestions",
            "problems",
        ]
        read_only_fields = [
            f
            for f in InspectionReportListSerializer.Meta.fields
            + [
                "asset_detail",
                "review_notes",
                "approved_by_name",
                "new_version_reason",
                "kit_checklist",
                "test_script",
                "has_storage",
                "required_photo_kinds",
                "photos",
                "findings",
                "erasures",
                "lot_tool",
                "suggestions",
                "problems",
            ]
        ]

    def get_asset_detail(self, obj) -> dict:
        return AssetSerializer(obj.asset, context=self.context).data

    def get_erasures(self, obj) -> list[dict]:
        return ErasureCertificateSerializer(
            obj.asset.erasures.select_related("tool", "operator", "removed_disk"),
            many=True,
            context=self.context,
        ).data

    def get_lot_tool(self, obj) -> dict | None:
        from .inspection import lot_tool

        definition = lot_tool(obj.asset)
        return (
            LotErasureToolSerializer(definition, context=self.context).data if definition else None
        )

    def get_suggestions(self, obj) -> dict:
        from .inspection import suggestions

        return suggestions(obj)

    def get_problems(self, obj) -> list[str]:
        from .inspection import problems

        return problems(obj) if obj.status == ReportStatus.DRAFT else []

    def get_approved_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.approved_by) if obj.approved_by else None

    def _code(self, domain, value):
        if value and value not in GRADE_CODES[domain]:
            raise serializers.ValidationError(_("Choose a valid level."))
        return value

    def validate_conservation(self, value):
        return self._code(GradeDomain.CONSERVATION, value)

    def validate_functioning(self, value):
        return self._code(GradeDomain.FUNCTIONING, value)

    def validate_completeness(self, value):
        return self._code(GradeDomain.COMPLETENESS, value)

    def validate_missing_items(self, value):
        kit = {
            e["item"].casefold(): e["item"] for e in self.instance.asset.asset_model.kit_checklist
        }
        if not isinstance(value, list) or any(str(v).casefold() not in kit for v in value):
            raise serializers.ValidationError(_("Choose items of the model's kit checklist."))
        return list(dict.fromkeys(kit[str(v).casefold()] for v in value))

    def validate_test_results(self, value):
        script = set(self.instance.asset.asset_model.test_script)
        if not isinstance(value, dict) or any(
            key not in script or result not in ("pass", "fail", "na")
            for key, result in value.items()
        ):
            raise serializers.ValidationError(_("Answer the checks of the model's test script."))
        return value


# --- Phase 4: deadlines, holidays, blocks, disputes, findings to charge, alerts -------------


class DeadlineSettingSerializer(serializers.ModelSerializer):
    reminder_days = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=60), required=False
    )

    class Meta:
        model = DeadlineSetting
        fields = ["id", "kind", "days", "business_days", "reminder_days", "updated_at"]
        read_only_fields = ["id", "kind", "updated_at"]
        extra_kwargs = {"days": {"min_value": 1, "max_value": 365}}

    def validate_reminder_days(self, value):
        return sorted(set(value), reverse=True)


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "name"]

    def validate_name(self, value):
        value = collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value


class AgingLimitSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgingLimit
        fields = ["id", "status", "days"]
        read_only_fields = ["id", "status"]
        extra_kwargs = {"days": {"min_value": 1, "max_value": 3650}}


class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidence
        fields = ["id", "name", "size", "content_type", "uploaded_at"]
        read_only_fields = fields


def _asset_summary(asset) -> dict:
    return {
        "id": asset.id,
        "horizon_id": asset.horizon_id,
        "model": _model_label(asset.asset_model),
        "serial": asset.serial,
        "status": asset.status,
        "customer": _customer_name(asset.customer),
        "lot": asset.lot.code if asset.lot_id else None,
        "location": asset.current_location.code,
    }


class BlockFollowUpSerializer(serializers.ModelSerializer):
    asset_detail = serializers.SerializerMethodField()
    report = serializers.IntegerField(source="finding.report_id", read_only=True)
    finding_value = serializers.DecimalField(
        source="finding.value", max_digits=12, decimal_places=2, read_only=True
    )
    finding_status = serializers.CharField(source="finding.status", read_only=True)
    days_left = serializers.SerializerMethodField()
    checked_by_name = serializers.SerializerMethodField()
    decided_by_name = serializers.SerializerMethodField()
    evidence = EvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = BlockFollowUp
        fields = [
            "id",
            "asset",
            "asset_detail",
            "report",
            "block_type",
            "status",
            "notified_at",
            "due_date",
            "days_left",
            "release_reported_at",
            "checked_by_name",
            "checked_at",
            "decision",
            "decision_notes",
            "decided_by_name",
            "decided_at",
            "finding_value",
            "finding_status",
            "evidence",
            "created_at",
        ]
        read_only_fields = fields

    def get_asset_detail(self, obj) -> dict:
        return _asset_summary(obj.asset)

    def get_days_left(self, obj) -> int | None:
        from .deadlines import days_left

        return days_left(timezone.localdate(), obj.due_date) if obj.due_date else None

    def get_checked_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.checked_by) if obj.checked_by else None

    def get_decided_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.decided_by) if obj.decided_by else None


class DisputeSerializer(serializers.ModelSerializer):
    asset_detail = serializers.SerializerMethodField()
    report_version = serializers.IntegerField(source="report.version", read_only=True)
    report_technician = serializers.IntegerField(source="report.technician_id", read_only=True)
    findings_detail = FindingSerializer(source="findings", many=True, read_only=True)
    registered_by_name = serializers.SerializerMethodField()
    analyst_name = serializers.SerializerMethodField()
    evidence = EvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = Dispute
        fields = [
            "id",
            "report",
            "report_version",
            "report_technician",
            "asset_detail",
            "findings",
            "findings_detail",
            "justification",
            "registered_by_name",
            "registered_at",
            "analysis_due",
            "analyst",
            "analyst_name",
            "reinspected",
            "status",
            "decision",
            "decision_notes",
            "new_report",
            "decided_at",
            "evidence",
        ]
        read_only_fields = fields

    def get_asset_detail(self, obj) -> dict:
        return _asset_summary(obj.report.asset)

    def get_registered_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.registered_by)

    def get_analyst_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.analyst) if obj.analyst else None


class ChargeFindingSerializer(FindingSerializer):
    """A finding to charge: with its asset, customer and report."""

    asset_detail = serializers.SerializerMethodField()
    report_id = serializers.IntegerField(source="report.id", read_only=True)

    class Meta(FindingSerializer.Meta):
        fields = FindingSerializer.Meta.fields + ["asset_detail", "report_id"]
        read_only_fields = fields

    def get_asset_detail(self, obj) -> dict:
        return _asset_summary(obj.report.asset)


class AlertSerializer(serializers.ModelSerializer):
    read = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Alert
        fields = ["id", "kind", "params", "ref", "created_at", "read"]
        read_only_fields = fields


# --- Phase 5: stock and disposals ----------------------------------------------------------


def asset_class_name(asset_class, *, many: bool = False) -> str:
    """The asset class's name in the active language (English when not translated)."""
    from django.utils.translation import get_language

    from catalogs.names import english_plural, localized

    return localized(
        asset_class.name,
        asset_class.plural_name or english_plural(asset_class.name),
        asset_class.translations,
        (get_language() or "en").lower(),
        many=many,
    )


class StockAssetSerializer(serializers.ModelSerializer):
    """An asset of the stock query with its current report's data (for pricing — spec §11)."""

    model = serializers.SerializerMethodField()
    asset_class = serializers.SerializerMethodField()
    warehouse = serializers.CharField(source="current_location.warehouse.code", read_only=True)
    location = serializers.CharField(source="current_location.code", read_only=True)
    customer = serializers.SerializerMethodField()
    lot = serializers.SerializerMethodField()
    days_in_stock = serializers.SerializerMethodField()
    report = serializers.SerializerMethodField()
    disposal = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            "id",
            "horizon_id",
            "serial",
            "model",
            "asset_class",
            "specs",
            "status",
            "condition_grade",
            "held_for_dispute",
            "warehouse",
            "location",
            "customer",
            "lot",
            "created_at",
            "days_in_stock",
            "report",
            "disposal",
        ]
        read_only_fields = fields

    def get_model(self, obj):
        return _model_label(obj.asset_model)

    def get_asset_class(self, obj):
        return asset_class_name(obj.asset_model.asset_class)

    def get_customer(self, obj):
        return _customer_name(obj.customer)

    def get_lot(self, obj):
        return obj.lot.code if obj.lot_id else None

    def get_days_in_stock(self, obj):
        return (timezone.localdate() - timezone.localtime(obj.created_at).date()).days

    def get_report(self, obj):
        current = getattr(obj, "current_reports", None)
        report = current[0] if current else None
        if report is None:
            return None
        return {
            "id": report.id,
            "version": report.version,
            "conservation": report.conservation,
            "functioning": report.functioning,
            "completeness": report.completeness,
            "missing_items": report.missing_items,
            "approved_at": report.approved_at,
        }

    def get_disposal(self, obj):
        items = getattr(obj, "open_disposal_items", None)
        if not items:
            return None
        return {"id": items[0].disposal_id, "code": items[0].disposal.code}


class DisposalFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DisposalFile
        fields = ["id", "kind", "name", "size", "content_type", "uploaded_at", "uploaded_by_name"]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        return display_name_in(self.context, obj.uploaded_by)


class DisposalItemSerializer(serializers.ModelSerializer):
    asset_detail = serializers.SerializerMethodField()
    accessory_model_label = serializers.SerializerMethodField()
    picked = serializers.BooleanField(read_only=True)
    picked_by_name = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = DisposalItem
        fields = [
            "id",
            "asset",
            "asset_detail",
            "accessory_model",
            "accessory_model_label",
            "quantity",
            "condition",
            "unit_value",
            "line_total",
            "picked_quantity",
            "picked",
            "picked_at",
            "picked_by_name",
        ]
        read_only_fields = fields

    def get_asset_detail(self, obj):
        if obj.asset is None:
            return None
        asset = obj.asset
        return {
            **_asset_summary(asset),
            "asset_class": asset_class_name(asset.asset_model.asset_class),
            "grade": asset.condition_grade,
            "held_for_dispute": asset.held_for_dispute,
            "area_type": asset.current_location.area_type,
        }

    def get_accessory_model_label(self, obj):
        return _model_label(obj.accessory_model) if obj.accessory_model_id else None

    def get_picked_by_name(self, obj):
        return display_name_in(self.context, obj.picked_by) if obj.picked_by else None

    def get_line_total(self, obj):
        if obj.unit_value is None:
            return None
        return f"{obj.unit_value * obj.quantity:.2f}"


class DisposalSerializer(serializers.ModelSerializer):
    """Header of a disposal. Writing: kind and warehouse only on creation; the rest while open.
    The detail adds `items`, `files`, `totals` and `problems` (what keeps it from shipping)."""

    code = serializers.CharField(read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    customer_name = serializers.SerializerMethodField()
    discard_provider_name = serializers.SerializerMethodField()
    appointment_code = serializers.SerializerMethodField()
    items_count = serializers.IntegerField(read_only=True, default=None)
    picked_count = serializers.IntegerField(read_only=True, default=None)
    created_by_name = serializers.SerializerMethodField()
    shipped_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()
    keywords = KeywordsField(required=False)

    class Meta:
        model = Disposal
        fields = [
            "id",
            "code",
            "kind",
            "status",
            "warehouse",
            "warehouse_code",
            "warehouse_name",
            "customer",
            "customer_name",
            "contract",
            "discard_provider",
            "discard_provider_name",
            "appointment",
            "appointment_code",
            "document_number",
            "notes",
            "keywords",
            "items_count",
            "picked_count",
            "created_by_name",
            "created_at",
            "updated_at",
            "shipped_by_name",
            "shipped_at",
            "cancelled_by_name",
            "cancelled_at",
            "cancel_reason",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_at",
            "updated_at",
            "shipped_at",
            "cancelled_at",
            "cancel_reason",
        ]

    def get_customer_name(self, obj):
        return _customer_name(obj.customer)

    def get_discard_provider_name(self, obj):
        provider = obj.discard_provider
        return (provider.trade_name or provider.name) if provider else None

    def get_appointment_code(self, obj):
        return obj.appointment.code if obj.appointment_id else None

    def get_created_by_name(self, obj):
        return display_name_in(self.context, obj.created_by)

    def get_shipped_by_name(self, obj):
        return display_name_in(self.context, obj.shipped_by) if obj.shipped_by else None

    def get_cancelled_by_name(self, obj):
        return display_name_in(self.context, obj.cancelled_by) if obj.cancelled_by else None


# --- Phase 6: transfers ----------------------------------------------------------------------


class TransferFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TransferFile
        fields = ["id", "kind", "name", "size", "content_type", "uploaded_at", "uploaded_by_name"]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        return display_name_in(self.context, obj.uploaded_by)


class TransferItemSerializer(serializers.ModelSerializer):
    asset_detail = serializers.SerializerMethodField()
    accessory_model_label = serializers.SerializerMethodField()
    container_code = serializers.CharField(source="container.code", read_only=True, default=None)
    received_location_code = serializers.CharField(
        source="received_location.code", read_only=True, default=None
    )
    picked = serializers.BooleanField(read_only=True)
    received = serializers.BooleanField(read_only=True)

    class Meta:
        model = TransferItem
        fields = [
            "id",
            "asset",
            "asset_detail",
            "accessory_model",
            "accessory_model_label",
            "quantity",
            "condition",
            "status_before",
            "container",
            "container_code",
            "picked_quantity",
            "picked",
            "picked_at",
            "received_quantity",
            "received",
            "received_at",
            "received_location_code",
        ]
        read_only_fields = fields

    def get_asset_detail(self, obj):
        if obj.asset is None:
            return None
        asset = obj.asset
        return {
            **_asset_summary(asset),
            "asset_class": asset_class_name(asset.asset_model.asset_class),
            "grade": asset.condition_grade,
            "held_for_dispute": asset.held_for_dispute,
            "container": asset.current_container.code if asset.current_container_id else None,
        }

    def get_accessory_model_label(self, obj):
        return _model_label(obj.accessory_model) if obj.accessory_model_id else None


class TransferSerializer(serializers.ModelSerializer):
    """Header of a transfer. Origin and destination only on creation. The detail adds
    `items`, `files`, `occurrences`, `problems` (what keeps it from being sent) and
    `days_late`."""

    code = serializers.CharField(read_only=True)
    origin_code = serializers.CharField(source="origin.code", read_only=True)
    origin_name = serializers.CharField(source="origin.name", read_only=True)
    destination_code = serializers.CharField(source="destination.code", read_only=True)
    destination_name = serializers.CharField(source="destination.name", read_only=True)
    items_count = serializers.IntegerField(read_only=True, default=None)
    picked_count = serializers.IntegerField(read_only=True, default=None)
    received_count = serializers.IntegerField(read_only=True, default=None)
    requested_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    sent_by_name = serializers.SerializerMethodField()
    received_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()
    days_late = serializers.SerializerMethodField()
    keywords = KeywordsField(required=False)

    class Meta:
        model = Transfer
        fields = [
            "id",
            "code",
            "origin",
            "origin_code",
            "origin_name",
            "destination",
            "destination_code",
            "destination_name",
            "reason",
            "status",
            "fiscal_document_number",
            "transit_days",
            "notes",
            "keywords",
            "items_count",
            "picked_count",
            "received_count",
            "requested_by_name",
            "requested_at",
            "approved_by_name",
            "approved_at",
            "sent_by_name",
            "sent_at",
            "received_by_name",
            "received_at",
            "cancelled_by_name",
            "cancelled_at",
            "cancel_reason",
            "days_late",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "requested_at",
            "approved_at",
            "sent_at",
            "received_at",
            "cancelled_at",
            "cancel_reason",
            "updated_at",
        ]

    def _name(self, user):
        return display_name_in(self.context, user) if user else None

    def get_requested_by_name(self, obj):
        return self._name(obj.requested_by)

    def get_approved_by_name(self, obj):
        return self._name(obj.approved_by)

    def get_sent_by_name(self, obj):
        return self._name(obj.sent_by)

    def get_received_by_name(self, obj):
        return self._name(obj.received_by)

    def get_cancelled_by_name(self, obj):
        return self._name(obj.cancelled_by)

    def get_days_late(self, obj):
        from .transfers import days_late

        return days_late(obj, timezone.localdate())


# --- Phase 7: inventory counts ----------------------------------------------------------------


class InventoryCountSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    responsible_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()
    locations_count = serializers.IntegerField(read_only=True, default=0)
    readings_count = serializers.IntegerField(read_only=True, default=0)
    pending_count = serializers.IntegerField(read_only=True, default=0)
    divergences_count = serializers.IntegerField(read_only=True, default=0)
    accuracy = serializers.SerializerMethodField()

    class Meta:
        model = InventoryCount
        fields = [
            "id",
            "code",
            "warehouse",
            "warehouse_code",
            "warehouse_name",
            "kind",
            "status",
            "responsible",
            "responsible_name",
            "notes",
            "locations_count",
            "readings_count",
            "divergences_count",
            "pending_count",
            "expected_assets",
            "matched_assets",
            "accuracy",
            "created_by_name",
            "created_at",
            "closed_by_name",
            "closed_at",
            "finished_at",
            "cancelled_at",
            "cancel_reason",
        ]
        read_only_fields = fields

    def get_responsible_name(self, obj):
        return display_name_in(self.context, obj.responsible)

    def get_created_by_name(self, obj):
        return display_name_in(self.context, obj.created_by)

    def get_closed_by_name(self, obj):
        return display_name_in(self.context, obj.closed_by) if obj.closed_by else None

    def get_accuracy(self, obj):
        from .indicators import ratio

        if obj.status not in ("closed", "finished"):
            return None
        value = ratio(obj.matched_assets, obj.expected_assets)
        return str(value) if value is not None else None


class CountReadingSerializer(serializers.ModelSerializer):
    location_code = serializers.CharField(source="location.code", read_only=True)
    asset_code = serializers.CharField(source="asset.horizon_id", read_only=True, default=None)
    asset_model_label = serializers.SerializerMethodField()
    container_code = serializers.CharField(source="container.code", read_only=True, default=None)
    counted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CountReading
        fields = [
            "id",
            "location",
            "location_code",
            "asset",
            "asset_code",
            "accessory_model",
            "asset_model_label",
            "container",
            "container_code",
            "quantity",
            "condition",
            "counted_by_name",
            "counted_at",
        ]
        read_only_fields = fields

    def get_asset_model_label(self, obj):
        model = obj.asset.asset_model if obj.asset_id else obj.accessory_model
        return _model_label(model)

    def get_counted_by_name(self, obj):
        return display_name_in(self.context, obj.counted_by)


class CountDivergenceSerializer(serializers.ModelSerializer):
    asset_code = serializers.CharField(source="asset.horizon_id", read_only=True, default=None)
    asset_status = serializers.CharField(source="asset.status", read_only=True, default=None)
    model_label = serializers.SerializerMethodField()
    container_code = serializers.CharField(source="container.code", read_only=True, default=None)
    expected_location_code = serializers.CharField(
        source="expected_location.code", read_only=True, default=None
    )
    found_location_code = serializers.CharField(
        source="found_location.code", read_only=True, default=None
    )
    decided_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CountDivergence
        fields = [
            "id",
            "kind",
            "asset",
            "asset_code",
            "asset_status",
            "model_label",
            "condition",
            "container_code",
            "expected_location_code",
            "found_location_code",
            "expected_quantity",
            "counted_quantity",
            "status",
            "reason",
            "decided_by_name",
            "decided_at",
        ]
        read_only_fields = fields

    def get_model_label(self, obj):
        model = obj.asset.asset_model if obj.asset_id else obj.accessory_model
        return _model_label(model) if model else None

    def get_decided_by_name(self, obj):
        return display_name_in(self.context, obj.decided_by) if obj.decided_by else None
