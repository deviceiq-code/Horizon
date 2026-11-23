"""User-facing messages for failures talking to the internet or to SearXNG (system.web)."""

from django.utils.translation import gettext as _

from .web import WebError


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
