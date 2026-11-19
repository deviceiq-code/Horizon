from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import AccountManager


class AccountManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountManager
        fields = ["id", "full_name", "email", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

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
