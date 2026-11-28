from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from config.keywords import KeywordsField
from config.parties import CompanyFieldsMixin

from .models import ServiceKind, ServiceProvider


class ServiceProviderSerializer(CompanyFieldsMixin, serializers.ModelSerializer):
    services = serializers.ListField(
        child=serializers.ChoiceField(choices=ServiceKind.choices), allow_empty=True
    )
    keywords = KeywordsField()
    # Warehouses it runs (read-only; Asset Management › Inventory)
    warehouses_count = serializers.SerializerMethodField()

    class Meta:
        model = ServiceProvider
        fields = [
            "id",
            "name",
            "trade_name",
            "tax_id",
            "country",
            "services",
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
            "is_active",
            "notes",
            "keywords",
            "warehouses_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # Uniqueness of (country, tax_id) is checked in validate() with a friendlier message
        validators = []

    def get_warehouses_count(self, obj) -> int:
        count = getattr(obj, "warehouses_total", None)
        return count if count is not None else obj.warehouses.count()

    def validate_services(self, value):
        """At least one; no repeats; kept in the order of the choices."""
        chosen = set(value)
        if not chosen:
            raise serializers.ValidationError(_("Choose at least one service."))
        return [kind for kind in ServiceKind.values if kind in chosen]

    def validate(self, attrs):
        errors = self.address_errors(attrs)
        errors.update(
            self.tax_id_errors(attrs, _("A service provider with this tax ID already exists."))
        )
        # The warehouses it runs need it to keep providing warehousing
        if (
            "services" in attrs
            and self.instance is not None
            and ServiceKind.WAREHOUSING not in attrs["services"]
            and self.instance.warehouses.exists()
        ):
            errors["services"] = _(
                "This provider runs warehouses: warehousing cannot be removed from its services."
            )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
