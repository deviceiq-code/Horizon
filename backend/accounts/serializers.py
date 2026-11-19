from rest_framework import serializers

from .models import UserPreferences


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ["language", "theme", "updated_at"]
        read_only_fields = ["updated_at"]
