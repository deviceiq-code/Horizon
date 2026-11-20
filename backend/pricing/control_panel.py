"""Pricing control panel: /api/pricing/settings/ (GET: everyone signed in; PATCH:
administrators). See PricingSettings."""

from django.urls import path
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from users.display import display_name_in
from users.permissions import is_administrator

from .models import PricingSettings

MAX_PERCENT = 100


class PricingSettingsSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PricingSettings
        fields = [
            "compatible_percent",
            "below_percent",
            "above_percent",
            "validity_months",
            "accept_expired",
            "updated_at",
            "updated_by_name",
        ]
        read_only_fields = ["updated_at", "updated_by_name"]
        extra_kwargs = {
            "compatible_percent": {"max_value": MAX_PERCENT},
            "below_percent": {"max_value": MAX_PERCENT},
            "above_percent": {"max_value": MAX_PERCENT},
            "validity_months": {"max_value": 120},
        }

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
