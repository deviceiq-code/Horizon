"""System settings (administrators edit; everyone logged in sees what is enabled)."""

from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from users.permissions import is_administrator

from .models import SystemSettings
from .serializers import SystemSettingsSerializer
from .web import WebError, search_images


def web_error_message(error: WebError) -> str:
    """User-facing text for a failure talking to the internet or to SearXNG."""
    messages = {
        "json_disabled": _(
            "SearXNG refused the JSON format. Enable it in its settings.yml "
            "(search: formats: [html, json])."
        ),
        "unreachable": _("Could not reach the address."),
        "http_error": _("The site answered with an error."),
        "bad_response": _("SearXNG did not answer with JSON."),
        "invalid_url": _("Enter a web address starting with http:// or https://."),
        "blocked_address": _("Addresses on the local network are not allowed."),
        "not_image": _("The address is not a JPEG, PNG, GIF or WebP image."),
        "too_large": _("The image is too large."),
    }
    return messages.get(error.code, _("Could not reach the address."))


def _data(request, obj):
    data = {
        "photo_search_enabled": bool(obj.searxng_url),
    }
    if is_administrator(request.user):
        data.update(SystemSettingsSerializer(obj).data)
    return data


@api_view(["GET", "PATCH"])
def system_settings(request):
    """GET: what is enabled (plus every setting for administrators). PATCH: administrators."""
    obj = SystemSettings.current()
    if request.method == "PATCH":
        if not is_administrator(request.user):
            return Response(
                {"detail": _("Only administrators can change the system settings.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SystemSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
    return Response(_data(request, obj))


@api_view(["POST"])
def test_searxng(request):
    """Try a search on the SearXNG URL given (not saved). Administrators only."""
    if not is_administrator(request.user):
        return Response(
            {"detail": _("Only administrators can change the system settings.")},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = SystemSettingsSerializer(data={"searxng_url": request.data.get("searxng_url")})
    serializer.is_valid(raise_exception=True)
    url = serializer.validated_data["searxng_url"]
    if not url:
        return Response(
            {"searxng_url": [_("This field may not be blank.")]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        results = search_images(url, "excavator", limit=50)
    except WebError as exc:
        return Response({"detail": web_error_message(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    return Response({"results": len(results)})
