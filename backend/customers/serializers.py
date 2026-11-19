import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Customer
from .tax_ids import brazilian_tax_id_kind, normalize_tax_id

BRAZILIAN_STATES = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}  # fmt: skip

_COUNTRY = re.compile(r"^[A-Z]{2}$")


def _collapse_spaces(value: str) -> str:
    return " ".join((value or "").split())


class CustomerSerializer(serializers.ModelSerializer):
    # Write: primary_account_manager (id, required) and secondary_account_managers (ids).
    # Read: also names, for display.
    primary_account_manager_name = serializers.SerializerMethodField()
    secondary_account_managers_detail = serializers.SerializerMethodField()

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"secondary_account_managers": {"required": False}}
        # Uniqueness of (country, tax_id) is checked in validate() with a friendlier message
        validators = []

    def get_primary_account_manager_name(self, obj) -> str:
        return obj.primary_account_manager.full_name

    def get_secondary_account_managers_detail(self, obj) -> list[dict]:
        managers = sorted(obj.secondary_account_managers.all(), key=lambda m: m.full_name.lower())
        return [{"id": m.id, "full_name": m.full_name} for m in managers]

    # --- Field normalization ------------------------------------------------------------------

    def validate_name(self, value):
        value = _collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate_trade_name(self, value):
        return _collapse_spaces(value)

    def validate_tax_id(self, value):
        value = normalize_tax_id(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate_country(self, value):
        value = (value or "").strip().upper()
        if not _COUNTRY.match(value):
            raise serializers.ValidationError(_("Enter a two-letter country code (ISO 3166-1)."))
        return value

    def validate_email(self, value):
        return (value or "").strip().lower()

    def validate_phone(self, value):
        return _collapse_spaces(value)

    def validate_state(self, value):
        return _collapse_spaces(value).upper()

    def validate_city(self, value):
        return _collapse_spaces(value)

    # --- Cross-field rules (they depend on the country) --------------------------------------

    def validate(self, attrs):
        def current(field, default=""):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, default) if self.instance else default

        country = current("country", "BR") or "BR"
        tax_id = current("tax_id")
        errors = {}

        if country == "BR":
            if "tax_id" in attrs or "country" in attrs:
                if brazilian_tax_id_kind(tax_id) is None:
                    errors["tax_id"] = _("Enter a valid CPF or CNPJ.")
            if "postal_code" in attrs and attrs["postal_code"]:
                digits = re.sub(r"\D", "", attrs["postal_code"])
                if len(digits) != 8:
                    errors["postal_code"] = _("Enter a valid CEP (8 digits).")
                else:
                    attrs["postal_code"] = digits
            state = current("state")
            if ("state" in attrs or "country" in attrs) and state and state not in BRAZILIAN_STATES:
                errors["state"] = _("Enter a valid Brazilian state (e.g. SP).")
        elif "postal_code" in attrs:
            attrs["postal_code"] = attrs["postal_code"].strip().upper()

        if "tax_id" not in errors and tax_id:
            duplicates = Customer.objects.filter(country=country, tax_id=tax_id)
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                errors["tax_id"] = _("A customer with this tax ID already exists.")

        # The primary account manager is not also a secondary one
        primary = current("primary_account_manager", None)
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
