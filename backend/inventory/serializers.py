import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from catalogs.models import Vertical
from config.keywords import KeywordsField
from config.parties import AddressFieldsMixin, collapse_spaces
from service_providers.models import ServiceKind
from users.display import display_name_in

from .codes import ASSET_PREFIX, format_code
from .models import Asset, Container, LabelRange, Location, MovementEvent, Ownership, Warehouse
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


class AssetEntrySerializer(serializers.Serializer):
    """Manual entry of an asset at a dock (until the triage of Phase 2)."""

    asset_model = serializers.IntegerField()
    location = serializers.CharField(help_text="Location or container code read at the dock")
    horizon_id = serializers.CharField(required=False, allow_blank=True, default="")
    serial = serializers.CharField(required=False, allow_blank=True, default="", max_length=100)
    no_serial_reason = serializers.CharField(required=False, allow_blank=True, default="")
    other_ids = serializers.DictField(required=False, default=dict)
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=300)


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

    class Meta:
        model = MovementEvent
        fields = [
            "id",
            "kind",
            "asset",
            "asset_code",
            "container",
            "container_code",
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


class MovementSerializer(serializers.Serializer):
    """POST /movements/: the object read (asset or container) and the destination read
    (location, or a container for an asset)."""

    object_code = serializers.CharField(max_length=80)
    destination_code = serializers.CharField(max_length=80)
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
