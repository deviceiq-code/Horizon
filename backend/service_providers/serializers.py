"""Service providers as pickers and other modules read them: the Service Provider role with
its entity's identification, contact and address (flat, as when they lived here). Written
through business entities (`entities.serializers`)."""

from rest_framework import serializers

from .models import ServiceProvider

ENTITY_FIELDS = [
    "name",
    "trade_name",
    "tax_id",
    "country",
    "contact_name",
    "email",
    "phone",
    "postal_code",
    "street",
    "number",
    "complement",
    "district",
    "city",
    "state",
    "notes",
    "keywords",
]


class ServiceProviderSerializer(serializers.ModelSerializer):
    # Active in the role and as an entity
    is_active = serializers.BooleanField(source="is_usable", read_only=True)
    # Warehouses it runs (Asset Management › Inventory)
    warehouses_count = serializers.SerializerMethodField()

    class Meta:
        model = ServiceProvider
        fields = [
            "id",
            "entity",
            *ENTITY_FIELDS,
            "services",
            "is_active",
            "warehouses_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_fields(self):
        fields = super().get_fields()
        for name in ENTITY_FIELDS:
            fields[name] = serializers.ReadOnlyField(source=f"entity.{name}")
        return fields

    def get_warehouses_count(self, obj) -> int:
        count = getattr(obj, "warehouses_total", None)
        return count if count is not None else obj.warehouses.count()
