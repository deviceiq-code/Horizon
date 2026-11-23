from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from config.keywords import KeywordsField
from config.parties import CompanyFieldsMixin
from users.display import full_name_in, person_ref
from users.models import is_account_manager

from .models import Customer


class CustomerSerializer(CompanyFieldsMixin, serializers.ModelSerializer):
    # Write: primary_account_manager (id, required) and secondary_account_managers (ids).
    # Read: also names, for display.
    primary_account_manager_name = serializers.SerializerMethodField()
    secondary_account_managers_detail = serializers.SerializerMethodField()
    keywords = KeywordsField()

    class Meta:
        model = Customer
        fields = [
            "id",
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
            "primary_account_manager",
            "primary_account_manager_name",
            "secondary_account_managers",
            "secondary_account_managers_detail",
            "is_active",
            "notes",
            "keywords",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"secondary_account_managers": {"required": False}}
        # Uniqueness of (country, tax_id) is checked in validate() with a friendlier message
        validators = []

    def get_primary_account_manager_name(self, obj) -> str:
        return full_name_in(self.context, obj.primary_account_manager)

    def get_secondary_account_managers_detail(self, obj) -> list[dict]:
        refs = [person_ref(self.context, m) for m in obj.secondary_account_managers.all()]
        return sorted(refs, key=lambda ref: ref["full_name"].lower())

    def validate_primary_account_manager(self, value):
        if not is_account_manager(value):
            raise serializers.ValidationError(_("This user is not an account manager."))
        return value

    def validate_secondary_account_managers(self, value):
        if any(not is_account_manager(user) for user in value):
            raise serializers.ValidationError(_("This user is not an account manager."))
        return value

    # --- Cross-field rules (they depend on the country) --------------------------------------

    def validate(self, attrs):
        errors = self.address_errors(attrs)
        errors.update(self.tax_id_errors(attrs, _("A customer with this tax ID already exists.")))

        # The primary account manager is not also a secondary one
        primary = self.current(attrs, "primary_account_manager", None)
        if "secondary_account_managers" in attrs:
            secondaries = attrs["secondary_account_managers"]
        elif self.instance is not None:
            secondaries = list(self.instance.secondary_account_managers.all())
        else:
            secondaries = []
        if primary is not None and primary in secondaries:
            errors["secondary_account_managers"] = _(
                "The primary account manager cannot also be a secondary one."
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
