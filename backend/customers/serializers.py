"""Customers as pickers and other modules read them: the Customer role with its entity's
identification, contact and address (flat, as when they lived here). Written through business
entities (`entities.serializers`)."""

from rest_framework import serializers

from users.display import full_name_in, person_ref

from .models import Customer

ENTITY_FIELDS = [
    "name",
    "trade_name",
    "tax_id",
    "country",
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


class CustomerSerializer(serializers.ModelSerializer):
    primary_account_manager_name = serializers.SerializerMethodField()
    secondary_account_managers_detail = serializers.SerializerMethodField()
    # Active in the role and as an entity
    is_active = serializers.BooleanField(source="is_usable", read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "entity",
            *ENTITY_FIELDS,
            "contract_types",
            "primary_account_manager",
            "primary_account_manager_name",
            "secondary_account_managers",
            "secondary_account_managers_detail",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_fields(self):
        fields = super().get_fields()
        for name in ENTITY_FIELDS:
            fields[name] = serializers.ReadOnlyField(source=f"entity.{name}")
        return fields

    def get_primary_account_manager_name(self, obj) -> str:
        return full_name_in(self.context, obj.primary_account_manager)

    def get_secondary_account_managers_detail(self, obj) -> list[dict]:
        refs = [person_ref(self.context, m) for m in obj.secondary_account_managers.all()]
        return sorted(refs, key=lambda ref: ref["full_name"].lower())
