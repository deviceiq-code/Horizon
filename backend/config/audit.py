"""Who created and who last changed a record ("cadastro"), and when — every register keeps
them: `created_at` / `created_by` and `updated_at` / `updated_by`.

- Models: `created_by_field()` and `updated_by_field()` beside their `created_at` /
  `updated_at` (users PROTECT: someone who created records is deactivated, never deleted).
- Views: `AuditedViewSetMixin` fills them from the signed-in user on create and update.
- Serializers: `AuditedSerializerMixin` returns `created_by_name` / `updated_by_name` (as the
  viewer names users); list `AUDIT_FIELDS` in `Meta.fields`.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

AUDIT_FIELDS = ["created_at", "created_by_name", "updated_at", "updated_by_name"]


def created_by_field():
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )


def updated_by_field():
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("updated by"),
    )


def _signed_in(request):
    user = getattr(request, "user", None)
    return user if user is not None and user.is_authenticated else None


class AuditedViewSetMixin:
    """Fills created_by / updated_by with the signed-in user (a ModelViewSet's own saves)."""

    def perform_create(self, serializer):
        user = _signed_in(self.request)
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=_signed_in(self.request))


def touch(instance, request, *fields: str) -> None:
    """Saves `fields` of a record changed outside its serializer (e.g. a specification
    template), recording who changed it."""
    instance.updated_by = _signed_in(request)
    instance.save(update_fields=[*fields, "updated_by", "updated_at"])


class AuditedSerializerMixin(serializers.Serializer):
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    def get_created_by_name(self, obj) -> str | None:
        from users.display import display_name_in

        return display_name_in(self.context, obj.created_by) if obj.created_by_id else None

    def get_updated_by_name(self, obj) -> str | None:
        from users.display import display_name_in

        return display_name_in(self.context, obj.updated_by) if obj.updated_by_id else None
