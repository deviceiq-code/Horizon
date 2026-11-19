from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import AccountManager


class AccountManagerSerializer(serializers.ModelSerializer):
    # Write: list of business vertical IDs. Read: also id + name + enabled, for display.
    verticals_detail = serializers.SerializerMethodField()

    class Meta:
        model = AccountManager
        fields = [
            "id",
            "full_name",
            "email",
            "verticals",
            "verticals_detail",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"verticals": {"required": False}}

    def get_verticals_detail(self, obj) -> list[dict]:
        verticals = sorted(obj.verticals.all(), key=lambda v: v.name.lower())
        return [{"id": v.id, "name": v.name, "is_enabled": v.is_enabled} for v in verticals]

    def validate_full_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        duplicates = AccountManager.objects.filter(email__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                _("An account manager with this email already exists.")
            )
        return value
