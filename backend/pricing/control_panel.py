"""Pricing control panel: /api/pricing/settings/ (GET: everyone signed in; PATCH:
administrators). See PricingSettings."""

from django.conf import settings
from django.urls import path
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from users.display import display_name_in
from users.permissions import is_administrator

from .models import DEFAULT_REPORT_DISCLAIMER, PricingSettings

MAX_PERCENT = 100
MAX_DISCLAIMER = 4000


class PricingSettingsSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.SerializerMethodField()
    # The texts "Restore Default" brings back (read-only)
    report_disclaimer_defaults = serializers.SerializerMethodField()

    class Meta:
        model = PricingSettings
        fields = [
            "compatible_percent",
            "below_percent",
            "above_percent",
            "validity_months",
            "accept_expired",
            "report_disclaimer",
            "report_disclaimer_defaults",
            "updated_at",
            "updated_by_name",
        ]
        read_only_fields = ["updated_at", "updated_by_name", "report_disclaimer_defaults"]
        extra_kwargs = {
            "compatible_percent": {"max_value": MAX_PERCENT},
            "below_percent": {"max_value": MAX_PERCENT},
            "above_percent": {"max_value": MAX_PERCENT},
            "validity_months": {"max_value": 120},
        }

    def get_report_disclaimer_defaults(self, obj) -> dict:
        return DEFAULT_REPORT_DISCLAIMER

    def validate_report_disclaimer(self, value):
        """{language: text} — the languages of the system; sending some languages changes only
        those."""
        languages = {code for code, _name in settings.LANGUAGES}
        if not isinstance(value, dict) or not set(value) <= languages:
            raise serializers.ValidationError(
                gettext_lazy("Give a text for each language (%(languages)s).")
                % {"languages": ", ".join(sorted(languages))}
            )
        for text in value.values():
            if not isinstance(text, str):
                raise serializers.ValidationError(gettext_lazy("Each text must be text."))
            if len(text) > MAX_DISCLAIMER:
                raise serializers.ValidationError(
                    gettext_lazy("Each text may have up to %(max)d characters.")
                    % {"max": MAX_DISCLAIMER}
                )
        current = dict(self.instance.report_disclaimer) if self.instance else {}
        current.update({code: text.strip() for code, text in value.items()})
        return current

    def get_updated_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.updated_by) if obj.updated_by else None

    def validate(self, attrs):
        get = lambda key: attrs.get(key, getattr(self.instance, key))  # noqa: E731
        compatible = get("compatible_percent")
        errors = {}
        for key in ("below_percent", "above_percent"):
            if get(key) <= compatible:
                errors[key] = [
                    gettext_lazy("Must be greater than the compatible range (%(value)s%%).")
                    % {"value": compatible}
                ]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


@api_view(["GET", "PATCH"])
def pricing_settings(request):
    obj = PricingSettings.current()
    if request.method == "PATCH":
        if not is_administrator(request.user):
            return Response(
                {"detail": _("Only administrators can change the pricing settings.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = PricingSettingsSerializer(
            obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        obj.refresh_from_db()
    return Response(PricingSettingsSerializer(obj, context={"request": request}).data)


urlpatterns = [path("settings/", pricing_settings, name="pricing-settings")]
