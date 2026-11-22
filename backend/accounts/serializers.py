from rest_framework import serializers

from .models import UserPreferences


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = [
            "language",
            "theme",
            "color_theme",
            "ui_scale",
            "date_format",
            "time_format",
            "select_on_focus",
            "auto_scope",
            "scope_threshold",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
