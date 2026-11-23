import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from config.keywords import KeywordsField
from users.display import person_ref
from users.models import ACCOUNT_MANAGER

from .models import (
    MANUFACTURER_RATINGS,
    MAX_TERM_MONTHS,
    REMARKETING_RATINGS,
    AssetClass,
    Manufacturer,
    SubVertical,
    Vertical,
    general_names,
)
from .names import english_plural
from .specs import MAX_FIELDS, MAX_OPTIONS, SpecError, normalize_template


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
        fields = [
            "id",
            "name",
            "is_general",
            "risk",
            "allowed_terms",
            "recommended_term",
        ]
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
    # Read-only: the account managers who work in this vertical. Administrators assign them on
    # the user (Users → the user's verticals), not here.
    account_managers_detail = serializers.SerializerMethodField()
    sub_verticals = SubVerticalSerializer(many=True, required=False)
    keywords = KeywordsField()

    class Meta:
        model = Vertical
        fields = [
            "id",
            "name",
            "account_managers_detail",
            "is_enabled",
            "notes",
            "keywords",
            "sub_verticals",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_account_managers_detail(self, obj) -> list[dict]:
        refs = [
            person_ref(self.context, profile.user)
            for profile in obj.account_manager_profiles.all()
            if profile.user.is_active
            and any(role.key == ACCOUNT_MANAGER for role in profile.user.roles.all())
        ]
        return sorted(refs, key=lambda ref: ref["full_name"].lower())

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
                try:
                    sub.delete()
                except ProtectedError as exc:
                    raise serializers.ValidationError(
                        {
                            "sub_verticals": [
                                _(
                                    'The sub-vertical "%(name)s" is in use (asset classes '
                                    "or eFMV analyses) and cannot be removed."
                                )
                                % {"name": sub.name}
                            ]
                        }
                    ) from exc
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


# --- Asset lists ------------------------------------------------------------------------------


def remarketing_average_field():
    """Read-only average of the star ratings (catalogs.ratings.average_stars), e.g. "3.13"."""
    return serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)


class ManufacturerSerializer(serializers.ModelSerializer):
    remarketing_average = remarketing_average_field()
    keywords = KeywordsField()

    class Meta:
        model = Manufacturer
        fields = [
            "id",
            "name",
            *MANUFACTURER_RATINGS,
            "remarketing_average",
            "is_enabled",
            "keywords",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # Not filled in = 0 stars (model default); null is not accepted
        extra_kwargs = {field: {"allow_null": False} for field in MANUFACTURER_RATINGS}

    def validate_name(self, value):
        value = _collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        duplicates = Manufacturer.objects.filter(name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(_("A manufacturer with this name already exists."))
        return value


def sub_vertical_label(sub) -> str:
    """ "Industry / Yellow line"; the general one shows translated ("Industry / General")."""
    return f"{sub.vertical.name} / {sub.display_name}"


class SubVerticalOptionSerializer(serializers.ModelSerializer):
    """A sub-vertical as offered by pickers and forms (asset classes, average prices)."""

    name = serializers.CharField(source="display_name")
    label = serializers.SerializerMethodField()
    vertical = serializers.SerializerMethodField()

    class Meta:
        model = SubVertical
        fields = [
            "id",
            "name",
            "is_general",
            "label",
            "vertical",
            "allowed_terms",
            "recommended_term",
        ]

    def get_label(self, obj) -> str:
        return sub_vertical_label(obj)

    def get_vertical(self, obj) -> dict:
        v = obj.vertical
        return {"id": v.id, "name": v.name, "is_enabled": v.is_enabled}


_ICON = re.compile(r"^mdi-[a-z0-9]+(-[a-z0-9]+)*$")


class AssetClassSerializer(serializers.ModelSerializer):
    # Read-only: the sub-vertical with its label and vertical, for display
    sub_vertical_detail = SubVerticalOptionSerializer(source="sub_vertical", read_only=True)
    remarketing_average = remarketing_average_field()
    keywords = KeywordsField()

    class Meta:
        model = AssetClass
        fields = [
            "id",
            "name",
            "plural_name",
            "translations",
            "icon",
            "sub_vertical",
            "sub_vertical_detail",
            *REMARKETING_RATINGS,
            "remarketing_average",
            "keywords",
            "notes",
            "spec_template",
            "is_enabled",
            "created_at",
            "updated_at",
        ]
        # The template is edited through /api/catalogs/asset-classes/<id>/spec-template/
        read_only_fields = ["id", "spec_template", "created_at", "updated_at"]
        # Not filled in = 0 stars (model default); null is not accepted
        extra_kwargs = {
            **{field: {"allow_null": False} for field in REMARKETING_RATINGS},
            # Not sent: the English plural of the name (to_internal_value)
            "plural_name": {"required": False},
        }
        # Uniqueness of the name within the sub-vertical is checked in validate() (friendlier)
        validators = []

    def validate_name(self, value):
        value = _collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate_plural_name(self, value):
        value = _collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def to_internal_value(self, data):
        # Not sent (e.g. older clients): the English plural of the name, by the usual rules
        values = super().to_internal_value(data)
        if "name" in values and not values.get("plural_name") and "plural_name" not in data:
            values["plural_name"] = english_plural(values["name"])
        return values

    def validate_translations(self, value):
        """{"pt-br": {"name": "...", "plural": "..."}, ...}: the other languages, optional."""
        others = {code for code, _name in settings.LANGUAGES if code != "en"}
        if not isinstance(value, dict) or not set(value) <= others:
            raise serializers.ValidationError(
                _("Translations are given per language: %(languages)s.")
                % {"languages": ", ".join(sorted(others))}
            )
        clean = {}
        for code, entry in value.items():
            if not isinstance(entry, dict) or not set(entry) <= {"name", "plural"}:
                raise serializers.ValidationError(_("Each translation has a name and a plural."))
            texts = {key: _collapse_spaces(str(entry.get(key) or "")) for key in ("name", "plural")}
            if any(len(text) > 100 for text in texts.values()):
                raise serializers.ValidationError(
                    _("Ensure this field has no more than %(max)s characters.") % {"max": 100}
                )
            if any(texts.values()):
                clean[code] = texts
        return clean

    def validate_icon(self, value):
        value = (value or "").strip()
        if not _ICON.match(value):
            raise serializers.ValidationError(_("Choose an icon from the list."))
        return value

    def validate_sub_vertical(self, value):
        # Only sub-verticals of enabled verticals can be assigned; keeping one whose vertical
        # was disabled since is fine
        unchanged = self.instance is not None and self.instance.sub_vertical_id == value.id
        if not value.vertical.is_enabled and not unchanged:
            raise serializers.ValidationError(_("This business vertical is disabled."))
        return value

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", None))
        sub_vertical = attrs.get("sub_vertical", getattr(self.instance, "sub_vertical", None))
        if name and sub_vertical:
            duplicates = AssetClass.objects.filter(sub_vertical=sub_vertical, name__iexact=name)
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    {"name": [_("This sub-vertical already has an asset class with this name.")]}
                )
        return attrs


# --- Specification templates -----------------------------------------------------------------


def spec_messages() -> dict[str, str]:
    """Translated texts for catalogs.specs (built per request, in the user's language)."""
    return {
        "blank_label": _("This field may not be blank."),
        "duplicate_label": _("Field names must be unique within the template."),
        "invalid_kind": _("Choose a valid type."),
        "no_options": _("Add at least one item to the list."),
        "duplicate_option": _("The list items must be unique."),
        "too_many_options": _("Use at most %(max)d items.") % {"max": MAX_OPTIONS},
        "invalid_boolean": _("Choose yes or no."),
        "invalid_choice": _("Choose an item from the list."),
        "invalid_rating": _("Choose from 0 to 5 stars, in half steps."),
        "too_many": _("Use at most %(max)d fields.") % {"max": MAX_FIELDS},
        "too_long": _("Too long."),
        "required": _("This field is required."),
        "invalid_number": _("Enter a number."),
        "unknown_field": _("This field is not part of the template."),
    }


class SpecTemplateSerializer(serializers.Serializer):
    """The whole template of an asset class; saving replaces it."""

    fields = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    def validate_fields(self, value):
        try:
            return normalize_template(value, spec_messages())
        except SpecError as exc:
            raise serializers.ValidationError(exc.errors) from exc
