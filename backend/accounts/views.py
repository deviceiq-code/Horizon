"""Session authentication and user preferences for the Vue frontend."""

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from config import environments
from config.environments import LIVE
from system.messages import web_error_message
from system.web import WebError, search_images
from users.display import display_name
from users.models import UserProfile, user_photo_version
from users.permissions import is_administrator
from users.sync import sync_preferences, sync_users

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
        # Live or Development (config/environments.py): the database being used
        "environment": environments.current(),
    }


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Make sure the browser receives the csrftoken cookie."""
    return Response({"detail": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
def environments_view(request):
    """The environments the login page offers and the one in use (its cookie's)."""
    return Response({"environments": environments.available(), "current": environments.current()})


def _warn_administrators(kind: str, *, severity, user_id=None, **params) -> None:
    """Tell the administrators (in Live, where users are kept) about a sign-in that failed: a
    notification each attempt (they open Users searching for the user)."""
    from inventory.followups import alert
    from users.models import ADMINISTRATOR

    with environments.activate(LIVE):
        alert(
            f"{kind}:{params.get('username', '')}:{timezone.now().isoformat()}"[:120],
            kind,
            ref=f"user:{user_id}" if user_id else "",
            role_key=ADMINISTRATOR,
            severity=severity,
            **params,
        )


def _client_address(request) -> str:
    """Where the attempt came from (behind the proxy: the first address it forwarded)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", ""))[:45]


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    from inventory.models import AlertSeverity

    """Users are kept in Live (users/sync.py): checked there, whatever the environment; the
    environment must be one of theirs (else refused and the administrators warned)."""
    environment = environments.current()
    username = str(request.data.get("username", ""))[:150]
    with environments.activate(LIVE):
        user = authenticate(request, username=username, password=request.data.get("password", ""))
        allowed = UserProfile.for_user(user).environments if user is not None else []
        known = (
            get_user_model().objects.filter(username=username).values_list("pk", flat=True).first()
            if user is None
            else user.pk
        )
    if user is None:
        # Every failed attempt is told to the administrators
        _warn_administrators(
            "login_failed",
            severity=AlertSeverity.ERROR,
            user_id=known,
            username=username,
            environment=environment,
            address=_client_address(request),
        )
        return Response(
            {"detail": _("Invalid username or password.")}, status=status.HTTP_400_BAD_REQUEST
        )
    if environment not in allowed:
        _warn_administrators(
            "environment_denied",
            severity=AlertSeverity.WARNING,
            user_id=user.pk,
            username=user.username,
            environment=environment,
            address=_client_address(request),
        )
        return Response(
            {
                "detail": _(
                    "The %(environment)s environment is not available to you. The "
                    "administrators were told about this attempt."
                )
                % {"environment": environments.label(environment)},
                "code": "environment_denied",
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    if environment != LIVE:
        # This environment's copy of the users, up to date, then its own user
        sync_users()
        user = get_user_model().objects.get(pk=user.pk)
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

    # Kept in Live with the user (users/sync.py), copied to the other environments
    request.user.is_authenticated  # noqa: B018 (the session read here first)
    with environments.activate(LIVE):
        obj = UserPreferences.for_user(request.user)
        serializer = UserPreferencesSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = serializer.data
    sync_preferences(request.user.pk)
    # The response itself is already in the newly chosen language
    translation.activate(obj.language)
    request.LANGUAGE_CODE = obj.language
    return Response(data)


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
