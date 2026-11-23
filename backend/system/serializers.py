from rest_framework import serializers

from .models import SystemSettings


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = ["searxng_url", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_searxng_url(self, value):
        return value.strip().rstrip("/")
