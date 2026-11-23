from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from catalogs.models import Vertical
from config.keywords import KeywordsField
from config.parties import AddressFieldsMixin, collapse_spaces
from service_providers.models import ServiceKind

from .models import Ownership, Warehouse


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
        read_only_fields = ["id", "created_at", "updated_at"]
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
