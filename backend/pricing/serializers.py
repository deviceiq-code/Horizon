from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from catalogs.models import AssetClass, Manufacturer
from catalogs.serializers import spec_messages, sub_vertical_label
from catalogs.specs import SpecError, snapshot_values
from users.display import display_name_in

from .curves import anchor_value, increasing_terms, monthly_curve, percent_of
from .documents import opens_inline
from .models import AnchorMode, AveragePrice, Currency, PriceDocument, PricePoint

MAX_PERCENT = 999
CENTS = Decimal("0.01")


def _collapse_spaces(value: str) -> str:
    return " ".join((value or "").split())


# --- Read ------------------------------------------------------------------------------------


class PricePointSerializer(serializers.ModelSerializer):
    percent = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    class Meta:
        model = PricePoint
        fields = ["term_months", "mode", "amount", "value", "percent"]


class AveragePriceSerializer(serializers.ModelSerializer):
    """A row as listed: what is priced, the values per term and warnings."""

    vertical = serializers.SerializerMethodField()
    sub_vertical = serializers.SerializerMethodField()
    asset_class = serializers.SerializerMethodField()
    manufacturer = serializers.SerializerMethodField()
    points = PricePointSerializer(many=True, read_only=True)
    increasing_terms = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    # Documents of the row (all versions); annotated by the viewset
    documents_count = serializers.SerializerMethodField()
    # Id of the photo (changes when replaced; used to refresh the image); annotated
    photo_id = serializers.SerializerMethodField()
    # Where the photo came from, when downloaded from the internet ("" otherwise)
    photo_source_url = serializers.SerializerMethodField()

    class Meta:
        model = AveragePrice
        fields = [
            "id",
            "vertical",
            "sub_vertical",
            "asset_class",
            "manufacturer",
            "model",
            "description",
            "specs",
            "currency",
            "original_value",
            "points",
            "increasing_terms",
            "is_current",
            "supersedes",
            "created_at",
            "created_by_name",
            "deleted_at",
            "documents_count",
            "photo_id",
            "photo_source_url",
        ]
        read_only_fields = fields

    def get_documents_count(self, obj) -> int:
        return getattr(obj, "documents_count", 0) or 0

    def get_photo_id(self, obj) -> int | None:
        return getattr(obj, "photo_id", None)

    def get_photo_source_url(self, obj) -> str:
        return getattr(obj, "photo_source_url", None) or ""

    def get_vertical(self, obj) -> dict:
        v = obj.sub_vertical.vertical
        return {"id": v.id, "name": v.name}

    def get_sub_vertical(self, obj) -> dict:
        return {"id": obj.sub_vertical_id, "label": sub_vertical_label(obj.sub_vertical)}

    def get_asset_class(self, obj) -> dict:
        a = obj.asset_class
        return {"id": a.id, "name": a.name, "icon": a.icon}

    def get_manufacturer(self, obj) -> dict:
        return {"id": obj.manufacturer_id, "name": obj.manufacturer.name}

    def get_increasing_terms(self, obj) -> list[int]:
        """Terms worth more than the point before them: shown as a warning, not an error."""
        return obj.increasing_terms()

    def get_created_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.created_by)


class CurvePointSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    value = serializers.DecimalField(max_digits=14, decimal_places=2)
    percent = serializers.DecimalField(max_digits=7, decimal_places=2)
    is_anchor = serializers.BooleanField()


class AveragePriceDetailSerializer(AveragePriceSerializer):
    """A single row, with its value for every month (computed, see pricing.curves)."""

    curve = serializers.SerializerMethodField()

    class Meta(AveragePriceSerializer.Meta):
        fields = [*AveragePriceSerializer.Meta.fields, "curve"]
        read_only_fields = fields

    def get_curve(self, obj) -> list[dict]:
        return CurvePointSerializer([p._asdict() for p in obj.curve()], many=True).data


# --- Create (rows are never edited: a change is a new version) -------------------------------


class PricePointInputSerializer(serializers.Serializer):
    term_months = serializers.IntegerField(min_value=1)
    mode = serializers.ChoiceField(choices=AnchorMode.choices)
    amount = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=0)

    def validate(self, attrs):
        if attrs["mode"] == AnchorMode.PERCENT and attrs["amount"] > MAX_PERCENT:
            raise serializers.ValidationError(
                {"amount": [_("Enter a percentage up to %(max)d%%.") % {"max": MAX_PERCENT}]}
            )
        if attrs["mode"] == AnchorMode.VALUE and attrs["amount"] != attrs["amount"].quantize(CENTS):
            raise serializers.ValidationError(
                {"amount": [_("Use at most 2 decimal places for values.")]}
            )
        return attrs


class AveragePriceCreateSerializer(serializers.Serializer):
    asset_class = serializers.PrimaryKeyRelatedField(
        queryset=AssetClass.objects.select_related("sub_vertical__vertical")
    )
    manufacturer = serializers.PrimaryKeyRelatedField(queryset=Manufacturer.objects.all())
    model = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    specs = serializers.DictField(required=False, default=dict)
    currency = serializers.ChoiceField(choices=Currency.choices, default=Currency.BRL)
    original_value = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=CENTS)
    points = PricePointInputSerializer(many=True)
    # When given, the new row is a new version of this one (which stops being current)
    supersedes = serializers.PrimaryKeyRelatedField(
        queryset=AveragePrice.objects.all(), required=False, allow_null=True
    )

    def validate_model(self, value):
        value = _collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate_description(self, value):
        return (value or "").strip()

    def validate_asset_class(self, value):
        if not value.is_enabled:
            raise serializers.ValidationError(_("This asset class is disabled."))
        if not value.sub_vertical.vertical.is_enabled:
            raise serializers.ValidationError(_("This business vertical is disabled."))
        return value

    def validate_manufacturer(self, value):
        if not value.is_enabled:
            raise serializers.ValidationError(_("This manufacturer is disabled."))
        return value

    def validate_supersedes(self, value):
        if value is not None and (not value.is_current or value.deleted_at is not None):
            raise serializers.ValidationError(
                _("Only the current version of an average price can get a new version.")
            )
        return value

    def validate(self, attrs):
        errors = {}
        sub_vertical = attrs["asset_class"].sub_vertical

        # Terms: exactly the sub-vertical's allowed terms, each once
        given = [p["term_months"] for p in attrs["points"]]
        expected = sorted(sub_vertical.allowed_terms)
        if len(given) != len(set(given)) or sorted(given) != expected:
            errors["points"] = [
                _("Fill in exactly these terms (months): %(terms)s.")
                % {"terms": ", ".join(str(t) for t in expected)}
            ]

        # Specifications: the asset class's template, stored as a snapshot
        try:
            attrs["specs"] = snapshot_values(
                attrs["asset_class"].spec_template, attrs.get("specs") or {}, spec_messages()
            )
        except SpecError as exc:
            errors["specs"] = exc.errors

        if errors:
            raise serializers.ValidationError(errors)
        attrs["sub_vertical"] = sub_vertical
        return attrs

    def create(self, validated_data):
        points = validated_data.pop("points")
        previous = validated_data.pop("supersedes", None)
        original = validated_data["original_value"]
        with transaction.atomic():
            if previous is not None:
                # Lock it so two users cannot both create "the" next version
                previous = AveragePrice.objects.select_for_update().get(pk=previous.pk)
                if not previous.is_current or previous.deleted_at is not None:
                    raise serializers.ValidationError(
                        {
                            "supersedes": [
                                _(
                                    "Only the current version of an average price can get "
                                    "a new version."
                                )
                            ]
                        }
                    )
                previous.is_current = False
                previous.save(update_fields=["is_current"])
                # Newer versions may have been deleted: the new one goes after the newest of all
                newest = AveragePrice.objects.select_for_update().get(pk=previous.versions()[0].pk)
            else:
                newest = None
            row = AveragePrice.objects.create(
                **validated_data,
                supersedes=newest,
                # A new version keeps the row's documents
                **({"lineage": previous.lineage} if previous is not None else {}),
                created_by=self.context["request"].user,
            )
            PricePoint.objects.bulk_create(
                PricePoint(
                    average_price=row,
                    term_months=p["term_months"],
                    mode=p["mode"],
                    amount=p["amount"],
                    value=anchor_value(original, p["mode"], p["amount"]),
                )
                for p in points
            )
        return row


# --- Documents --------------------------------------------------------------------------------


class PriceDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    opens_inline = serializers.SerializerMethodField()

    class Meta:
        model = PriceDocument
        fields = [
            "id",
            "name",
            "size",
            "content_type",
            "opens_inline",
            "uploaded_at",
            "uploaded_by_name",
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj) -> str | None:
        return display_name_in(self.context, obj.uploaded_by)

    def get_opens_inline(self, obj) -> bool:
        return opens_inline(obj.name)


# --- Average of the versions (read-only) ----------------------------------------------------


class AverageTermSerializer(serializers.Serializer):
    term_months = serializers.IntegerField()
    value = serializers.DecimalField(max_digits=14, decimal_places=2)
    percent = serializers.DecimalField(max_digits=8, decimal_places=2)
    count = serializers.IntegerField()


class VersionsAverageSerializer(serializers.Serializer):
    """pricing.averages.VersionsAverage"""

    count = serializers.IntegerField()
    original_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    points = AverageTermSerializer(many=True)


# --- Preview (nothing is saved) --------------------------------------------------------------


class AveragePricePreviewSerializer(serializers.Serializer):
    """Resolve the points and the curve for values being typed, so the form never computes
    prices itself."""

    original_value = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=CENTS)
    points = PricePointInputSerializer(many=True, allow_empty=False)

    def validate_points(self, value):
        terms = [p["term_months"] for p in value]
        if len(terms) != len(set(terms)):
            raise serializers.ValidationError(_("Each term may appear only once."))
        return value

    def to_representation(self, instance):
        original = instance["original_value"]
        anchors = {
            p["term_months"]: anchor_value(original, p["mode"], p["amount"])
            for p in instance["points"]
        }
        return {
            "points": [
                {
                    "term_months": term,
                    "value": str(value),
                    "percent": str(percent_of(original, value)),
                }
                for term, value in sorted(anchors.items())
            ],
            "increasing_terms": increasing_terms(original, anchors),
            "curve": CurvePointSerializer(
                [p._asdict() for p in monthly_curve(original, anchors)], many=True
            ).data,
        }
