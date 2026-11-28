"""The word dictionary's API: /api/system/word-dictionary/ (GET: everyone signed in — the
browser applies it; writing: administrators). Each word: its spelling and the ways it may be
typed; no way of typing belongs to two words."""

from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, serializers, viewsets
from rest_framework.routers import DefaultRouter

from config.audit import AUDIT_FIELDS, AuditedSerializerMixin, AuditedViewSetMixin
from users.permissions import is_administrator

from .models import MAX_VARIANTS, MAX_WORD, DictionaryWord


def tidy(text: str) -> str:
    return " ".join(str(text).split())


class DictionaryWordSerializer(AuditedSerializerMixin, serializers.ModelSerializer):
    variants = serializers.ListField(
        child=serializers.CharField(max_length=MAX_WORD, allow_blank=True),
        required=False,
        max_length=MAX_VARIANTS,
    )

    class Meta:
        model = DictionaryWord
        fields = ["id", "replacement", "variants", *AUDIT_FIELDS]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_replacement(self, value):
        value = tidy(value)
        if not any(c.isalnum() for c in value):
            raise serializers.ValidationError(_("Type a word with letters or digits."))
        return value

    def validate(self, attrs):
        replacement = attrs.get("replacement", getattr(self.instance, "replacement", ""))
        variants, seen = [], {replacement.casefold()}
        for variant in attrs.get("variants", getattr(self.instance, "variants", [])):
            variant = tidy(variant)
            if not variant or variant.casefold() in seen:
                continue
            if not any(c.isalnum() for c in variant):
                raise serializers.ValidationError(
                    {"variants": [_("Each way to type it needs letters or digits.")]}
                )
            seen.add(variant.casefold())
            variants.append(variant)
        others = DictionaryWord.objects.exclude(pk=getattr(self.instance, "pk", None))
        taken = {}
        for word in others:
            for typed in [word.replacement, *word.variants]:
                taken[typed.casefold()] = word.replacement
        clash = next((typed for typed in seen if typed in taken), None)
        if clash is not None:
            raise serializers.ValidationError(
                {
                    "variants": [
                        _("“%(typed)s” already becomes “%(word)s”.")
                        % {"typed": clash, "word": taken[clash]}
                    ]
                }
            )
        attrs["variants"] = variants
        return attrs


class ReadAllWriteAdmins(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.method in permissions.SAFE_METHODS or is_administrator(request.user)


class DictionaryWordViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    queryset = DictionaryWord.objects.all()
    serializer_class = DictionaryWordSerializer
    permission_classes = [ReadAllWriteAdmins]
    # The whole dictionary at once (the browser keeps it)
    pagination_class = None


router = DefaultRouter()
router.register("word-dictionary", DictionaryWordViewSet, basename="word-dictionary")
from django.urls import path  # noqa: E402

from .journal import journal  # noqa: E402

urlpatterns = [path("journal/", journal, name="journal"), *router.urls]
