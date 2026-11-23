"""Session authentication and user preferences for the Vue frontend."""

from django.contrib.auth import authenticate, login, logout
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from system.messages import web_error_message
from system.web import WebError, search_images
from users.display import display_name
from users.models import user_photo_version
from users.permissions import is_administrator

from .models import UserPreferences
from .serializers import UserPreferencesSerializer


def _user_data(user):
    preferences = UserPreferences.for_user(user)
    return {
        "id": user.id,
        "username": user.username,
        # As the user wants users shown (username, first name or full name)
        "name": display_name(user, viewer=user),
        # Administrators can do everything (users, roles, system settings…)
        "is_admin": is_administrator(user),
        "roles": sorted(role.name for role in user.roles.all()),
        # The same roles for display: system ones (with a key) show translated in the UI
        "role_refs": [
            {"name": role.name, "key": role.key, "is_system": role.is_system}
            for role in sorted(user.roles.all(), key=lambda role: role.name)
        ],
        "email": user.email,
        # The user's photo (GET /api/users/<id>/photo/?v=<version>), null without one
        "photo_version": user_photo_version(user),
        "preferences": UserPreferencesSerializer(preferences).data,
    }


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Make sure the browser receives the csrftoken cookie."""
    return Response({"detail": "ok"})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    user = authenticate(
        request,
        username=request.data.get("username", ""),
        password=request.data.get("password", ""),
    )
    if user is None:
        return Response(
            {"detail": _("Invalid username or password.")}, status=status.HTTP_400_BAD_REQUEST
        )
    login(request, user)
    return Response(_user_data(user))


@api_view(["POST"])
def logout_view(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def me(request):
    return Response(_user_data(request.user))


@api_view(["GET", "PATCH"])
def preferences(request):
    """Read or partially update the logged-in user's preferences."""
    obj = UserPreferences.for_user(request.user)
    if request.method == "GET":
        return Response(UserPreferencesSerializer(obj).data)

    serializer = UserPreferencesSerializer(obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # The response itself is already in the newly chosen language
    translation.activate(obj.language)
    request.LANGUAGE_CODE = obj.language
    return Response(serializer.data)


@api_view(["POST"])
def test_searxng(request):
    """Try a search on the SearXNG address given (not saved): how many images came."""
    serializer = UserPreferencesSerializer(
        data={"searxng_url": request.data.get("searxng_url")}, partial=True
    )
    serializer.is_valid(raise_exception=True)
    url = serializer.validated_data.get("searxng_url", "")
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
