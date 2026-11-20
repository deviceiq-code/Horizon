"""User and role management (administrators only)."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.utils.translation import gettext as _
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.filters import NullsLastOrderingFilter
from config.photos import photo_response

from .models import ACCOUNT_MANAGER, ADMINISTRATOR, Role, UserProfile, is_account_manager
from .permissions import IsAdministrator, is_administrator
from .serializers import AccountManagerSerializer, RoleSerializer, UserSerializer

User = get_user_model()


def _conflict(message):
    return Response({"detail": message}, status=status.HTTP_409_CONFLICT)


def _administrators():
    """Active users who are administrators."""
    return (
        User.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(roles__key=ADMINISTRATOR))
        .distinct()
    )


class UserViewSet(viewsets.ModelViewSet):
    """Users of the system. ?search= (username, names, email, role), ?is_active=true|false,
    ?ordering= (username, first_name, last_name, email, last_login, date_joined). Nobody can
    delete or deactivate themselves or take the Administrator role from themselves, and at
    least one active administrator always remains. Users with records (prices, documents…)
    cannot be deleted: deactivate them instead; nor can account managers of customers, who also
    keep the Account Manager role. ?role=<id or system key>. Photo: GET/POST/DELETE
    /<id>/photo/."""

    queryset = User.objects.prefetch_related("roles", "profile__verticals").select_related(
        "profile__manager"
    )
    serializer_class = UserSerializer
    permission_classes = [IsAdministrator]
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = ["username", "first_name", "last_name", "email", "roles__name"]
    ordering_fields = [
        "id",
        "username",
        "first_name",
        "last_name",
        "email",
        "last_login",
        "date_joined",
    ]
    ordering = ["username"]

    def get_permissions(self):
        # Anyone signed in sees users' photos (e.g. their own in the top bar); the rest is for
        # administrators
        if self.action == "photo" and self.request.method == "GET":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        active = params.get("is_active")
        if active in ("true", "false"):
            queryset = queryset.filter(is_active=active == "true")
        # ?role=<id> or a system role's key (e.g. "account_manager")
        role = params.get("role", "")
        if role.isdigit():
            queryset = queryset.filter(roles__id=int(role))
        elif role:
            queryset = queryset.filter(roles__key=role)
        return queryset.distinct()

    def perform_update(self, serializer):
        user = serializer.instance
        data = serializer.validated_data
        is_self = user.pk == self.request.user.pk
        losing_admin = "roles" in data and not any(r.key == ADMINISTRATOR for r in data["roles"])
        losing_manager = "roles" in data and not any(
            r.key == ACCOUNT_MANAGER for r in data["roles"]
        )
        if losing_manager and is_account_manager(user) and _has_customers(user):
            raise _Refused(
                _(
                    "This user is the account manager of customers and must keep the Account "
                    "Manager role. Change those customers first."
                )
            )
        deactivating = data.get("is_active") is False
        if is_self and deactivating:
            raise _Refused(_("You cannot deactivate your own user."))
        if is_self and losing_admin and user.roles.filter(key=ADMINISTRATOR).exists():
            raise _Refused(_("You cannot remove the Administrator role from yourself."))
        with transaction.atomic():
            serializer.save()
            if not _administrators().exists():
                transaction.set_rollback(True)
                raise _Refused(_("At least one active administrator must remain."))

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except _Refused as exc:
            return _conflict(exc.message)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.pk == request.user.pk:
            return _conflict(_("You cannot delete your own user."))
        if _has_customers(user):
            return _conflict(
                _("This user has records in the system and cannot be deleted. Deactivate it.")
            )
        try:
            with transaction.atomic():
                user.delete()
                if not _administrators().exists():
                    transaction.set_rollback(True)
                    return _conflict(_("At least one active administrator must remain."))
        except ProtectedError:
            return _conflict(
                _("This user has records in the system and cannot be deleted. Deactivate it.")
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["get", "post", "delete"],
        url_path="photo",
        parser_classes=[MultiPartParser, FormParser],
    )
    def photo(self, request, pk=None):
        """GET (anyone signed in): the image. POST (multipart, "file"; administrators): set or
        replace it. DELETE (administrators): remove it."""
        user = self.get_object()
        return photo_response(
            request,
            UserProfile.for_user(user),
            can_change=is_administrator(request.user),
            saved_data=lambda _profile: self.get_serializer(User.objects.get(pk=user.pk)).data,
        )


def _has_customers(user) -> bool:
    """Primary or secondary account manager of any customer."""
    return user.primary_customers.exists() or user.secondary_customers.exists()


class AccountManagerViewSet(viewsets.ReadOnlyModelViewSet):
    """Account managers (active users with the "Account Manager" role) for pickers and lists,
    to everyone signed in. ?search= (name, email, vertical), ?vertical=<id>, ?ordering=
    (first_name, last_name, email). They are managed in Users (administrators)."""

    serializer_class = AccountManagerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "email", "profile__verticals__name"]
    ordering_fields = ["first_name", "last_name", "email"]
    ordering = ["first_name", "last_name"]

    def get_queryset(self):
        queryset = (
            User.objects.filter(is_active=True, roles__key=ACCOUNT_MANAGER)
            .select_related("profile")
            .prefetch_related("profile__verticals")
        )
        vertical = self.request.query_params.get("vertical", "")
        if vertical.isdigit():
            queryset = queryset.filter(profile__verticals__id=int(vertical))
        return queryset.distinct()


class _Refused(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class RoleViewSet(viewsets.ModelViewSet):
    """Roles users can have. ?search= (name, description), ?ordering= (name, users_count).
    System roles (Administrator, Account Manager) cannot be changed or deleted; roles with
    users cannot be deleted."""

    queryset = Role.objects.annotate(users_count=Count("users", distinct=True))
    serializer_class = RoleSerializer
    permission_classes = [IsAdministrator]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "users_count", "created_at"]
    ordering = ["name"]

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            return _conflict(_("System roles cannot be deleted."))
        if role.users.exists():
            return _conflict(_("This role is given to users and cannot be deleted."))
        role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
