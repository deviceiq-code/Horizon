from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import MAX_TERM_MONTHS, SubVertical, Vertical, general_names


def _collapse_spaces(value: str) -> str:
    return " ".join((value or "").split())


class SubVerticalSerializer(serializers.ModelSerializer):
    # Present: update that existing sub-vertical. Absent: create a new one.
    id = serializers.IntegerField(required=False)
    is_general = serializers.BooleanField(required=False, default=False)
    allowed_terms = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=MAX_TERM_MONTHS),
        allow_empty=False,
    )

    class Meta:
        model = SubVertical
        fields = ["id", "name", "is_general", "risk", "allowed_terms", "recommended_term"]
        extra_kwargs = {"name": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        errors = {}
        # Nested items are always validated as complete objects, even inside a PATCH
        for field in ("allowed_terms", "recommended_term"):
            if field not in attrs:
                errors[field] = [_("This field is required.")]
        if errors:
            raise serializers.ValidationError(errors)

        attrs["allowed_terms"] = sorted(set(attrs["allowed_terms"]))
        if attrs["recommended_term"] not in attrs["allowed_terms"]:
            errors["recommended_term"] = [
                _("The recommended term must be one of the allowed terms.")
            ]

        if attrs.get("is_general"):
            attrs["name"] = ""  # shown translated as "General"
        else:
            name = _collapse_spaces(attrs.get("name", ""))
            if not name:
                errors["name"] = [_("This field may not be blank.")]
            elif name.lower() in general_names():
                errors["name"] = [_("This name is reserved for the general sub-vertical.")]
            attrs["name"] = name

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class VerticalSerializer(serializers.ModelSerializer):
    # Read-only: the account managers who work in this vertical. They are assigned on the
    # account manager (AccountManager.verticals), not here.
    account_managers_detail = serializers.SerializerMethodField()
    sub_verticals = SubVerticalSerializer(many=True, required=False)

    class Meta:
        model = Vertical
        fields = [
            "id",
            "name",
            "account_managers_detail",
            "is_enabled",
            "notes",
            "sub_verticals",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_account_managers_detail(self, obj) -> list[dict]:
        managers = sorted(obj.account_managers.all(), key=lambda m: m.full_name.lower())
        return [{"id": m.id, "full_name": m.full_name} for m in managers]

    def validate_name(self, value):
        value = _collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        duplicates = Vertical.objects.filter(name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(_("A vertical with this name already exists."))
        return value

    def validate_sub_verticals(self, items):
        """The list replaces all sub-verticals: exactly one general, unique names."""
        if sum(1 for item in items if item.get("is_general")) != 1:
            raise serializers.ValidationError(_("Exactly one general sub-vertical is required."))

        names = [item["name"].lower() for item in items if not item.get("is_general")]
        if len(names) != len(set(names)):
            raise serializers.ValidationError(
                _("Sub-vertical names must be unique within the vertical.")
            )

        existing = {s.id: s for s in self.instance.sub_verticals.all()} if self.instance else {}
        for item in items:
            sub_id = item.get("id")
            if sub_id is None:
                # The general sub-vertical already exists: it must be updated, not re-created
                if item.get("is_general") and self.instance is not None:
                    raise serializers.ValidationError(
                        _("The general sub-vertical cannot be replaced.")
                    )
                continue
            current = existing.get(sub_id)
            if current is None:
                raise serializers.ValidationError(_("Unknown sub-vertical."))
            if current.is_general != bool(item.get("is_general")):
                raise serializers.ValidationError(_("The general sub-vertical cannot be replaced."))
        return items

    def create(self, validated_data):
        sub_verticals = validated_data.pop("sub_verticals", None)
        with transaction.atomic():
            vertical = Vertical.objects.create(**validated_data)
            if sub_verticals is None:
                sub_verticals = [SubVertical.general_defaults()]
            for item in sub_verticals:
                item.pop("id", None)
                SubVertical.objects.create(vertical=vertical, **item)
        return vertical

    def update(self, instance, validated_data):
        sub_verticals = validated_data.pop("sub_verticals", None)
        try:
            with transaction.atomic():
                instance = super().update(instance, validated_data)
                if sub_verticals is not None:
                    self._sync_sub_verticals(instance, sub_verticals)
        except IntegrityError as exc:
            # e.g. two sub-verticals swapping names in the same request
            raise serializers.ValidationError(
                {"sub_verticals": [_("Could not save the sub-verticals. Please try again.")]}
            ) from exc
        return instance

    @staticmethod
    def _sync_sub_verticals(vertical, items):
        existing = {s.id: s for s in vertical.sub_verticals.all()}
        kept_ids = {item["id"] for item in items if item.get("id") is not None}
        # Delete first, so a removed name can be reused by a new sub-vertical
        for sub_id, sub in existing.items():
            if sub_id not in kept_ids and not sub.is_general:
                sub.delete()
        for item in items:
            sub_id = item.pop("id", None)
            if sub_id is None:
                SubVertical.objects.create(vertical=vertical, **item)
                continue
            sub = existing[sub_id]
            item.pop("is_general", None)
            for field, value in item.items():
                setattr(sub, field, value)
            sub.save()
