import json

from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import MAX_UI_STATE_BYTES, UserPreferences


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
            "number_format",
            "percent_places",
            "currency",
            "currency_display",
            "ui_state",
            "user_name_display",
            "full_name_order",
            "searxng_url",
            "web_search",
            "web_search_engine",
            "select_on_focus",
            "auto_scope",
            "scope_threshold",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_searxng_url(self, value):
        return (value or "").strip().rstrip("/")

    def validate_ui_state(self, value):
        """An object of the interface's own state (not interpreted here), kept small."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("Expected an object."))
        if len(json.dumps(value)) > MAX_UI_STATE_BYTES:
            raise serializers.ValidationError(_("Too much interface state."))
        return value
