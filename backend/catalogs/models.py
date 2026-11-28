"""Reference data ("catalogs"): small tables used across the system, e.g. business verticals."""

from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import translation
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from config.audit import created_by_field, updated_by_field
from config.keywords import keywords_field

from .ratings import STARS_MAX, STARS_MIN, average_stars, is_half_star


class Vertical(models.Model):
    """A business vertical (industry segment), split into sub-verticals.

    The enabled flag and notes apply to all of its sub-verticals. Which account managers work
    in it is set on the user (UserProfile.verticals; here: `account_manager_profiles`).
    """

    name = models.CharField(_("name"), max_length=100)
    is_enabled = models.BooleanField(_("enabled"), default=True)
    notes = models.TextField(_("notes"), blank=True)
    keywords = keywords_field()
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    created_by = created_by_field()
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by = updated_by_field()

    class Meta:
        verbose_name = _("business vertical")
        verbose_name_plural = _("business verticals")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="vertical_unique_name"),
        ]

    def __str__(self):
        return self.name


class Risk(models.TextChoices):
    LOW = "low", _("Low")
    MEDIUM = "medium", _("Medium")
    HIGH = "high", _("High")


# Values for the "General" sub-vertical of a new vertical (the UI reads them from the API)
DEFAULT_RISK = Risk.MEDIUM
DEFAULT_TERMS = [12, 24, 36, 48, 60]
DEFAULT_RECOMMENDED_TERM = 36
MAX_TERM_MONTHS = 360


def general_names() -> set[str]:
    """Lowercase "General" in every supported language (reserved for the general sub-vertical)."""
    from django.conf import settings

    names = set()
    for code, _name in settings.LANGUAGES:
        with translation.override(code):
            names.add(gettext("General").lower())
    return names


class SubVertical(models.Model):
    """A segment within a vertical, e.g. Industry / Yellow line.

    Every vertical has exactly one general sub-vertical ("General"), created with it, which
    cannot be renamed or deleted. Its name is stored empty and shown translated.
    """

    vertical = models.ForeignKey(
        Vertical,
        on_delete=models.CASCADE,
        related_name="sub_verticals",
        verbose_name=_("business vertical"),
    )
    name = models.CharField(_("name"), max_length=100, blank=True)
    is_general = models.BooleanField(_("general"), default=False, editable=False)
    risk = models.CharField(_("risk"), max_length=10, choices=Risk, default=DEFAULT_RISK)
    allowed_terms = ArrayField(
        models.PositiveSmallIntegerField(),
        verbose_name=_("allowed terms (months)"),
    )
    recommended_term = models.PositiveSmallIntegerField(_("recommended term (months)"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("sub-vertical")
        verbose_name_plural = _("sub-verticals")
        ordering = ["-is_general", "name"]  # General first
        constraints = [
            models.UniqueConstraint(
                fields=["vertical"],
                condition=models.Q(is_general=True),
                name="sub_vertical_one_general_per_vertical",
            ),
            models.UniqueConstraint(
                "vertical", Lower("name"), name="sub_vertical_unique_name_per_vertical"
            ),
            models.CheckConstraint(
                condition=models.Q(is_general=True) | ~models.Q(name=""),
                name="sub_vertical_name_required",
            ),
        ]

    def __str__(self):
        return f"{self.vertical} / {self.display_name}"

    @property
    def display_name(self) -> str:
        return gettext("General") if self.is_general else self.name

    @staticmethod
    def general_defaults() -> dict:
        return {
            "is_general": True,
            "name": "",
            "risk": DEFAULT_RISK,
            "allowed_terms": list(DEFAULT_TERMS),
            "recommended_term": DEFAULT_RECOMMENDED_TERM,
        }


# --- Asset lists: manufacturers and asset classes ----------------------------------------------

# Remarketing ratings: 0–5 stars in half-star steps (e.g. 3.5). Not filled in = 0 stars.
# Their average is computed by catalogs.ratings.average_stars (not stored).
MANUFACTURER_RATINGS = ["reputation", "product_quality", "after_sales"]
REMARKETING_RATINGS = ["liquidity", "value_retention", "technology_renewal", "usage_breadth"]
DEFAULT_ASSET_ICON = "mdi-cube-outline"


def validate_half_star(value):
    if value is not None and not is_half_star(value):
        raise ValidationError(_("Use whole or half stars (e.g. 3.5)."))


def star_rating_field(verbose_name):
    """0–5 stars in half steps; 0 when not filled in."""
    return models.DecimalField(
        verbose_name,
        max_digits=2,
        decimal_places=1,
        default=Decimal("0"),
        validators=[
            MinValueValidator(STARS_MIN),
            MaxValueValidator(STARS_MAX),
            validate_half_star,
        ],
    )


def stars_range_constraints(prefix, fields):
    return [
        models.CheckConstraint(
            condition=models.Q(**{f"{field}__gte": STARS_MIN, f"{field}__lte": STARS_MAX}),
            name=f"{prefix}_{field}_range",
        )
        for field in fields
    ]


class Manufacturer(models.Model):
    """A maker of leased assets (e.g. a tractor or server brand).

    Its remarketing rating — how the brand performs in the used-equipment market — is made of
    three 0–5 star ratings:

    - reputation: how well the brand is accepted in the secondary market (0 not accepted,
      5 very well ranked);
    - product_quality: 0 very poor, 5 excellent;
    - after_sales: after-sales service, 0 very poor, 5 excellent.
    """

    name = models.CharField(_("name"), max_length=100)
    # The business entity behind the brand (optional; e.g. Dell → Dell Computadores do Brasil)
    business_entity = models.ForeignKey(
        "entities.BusinessEntity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="brands",
        verbose_name=_("business entity"),
    )
    reputation = star_rating_field(_("reputation"))
    product_quality = star_rating_field(_("product quality"))
    after_sales = star_rating_field(_("after-sales service"))
    keywords = keywords_field()
    is_enabled = models.BooleanField(_("enabled"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    created_by = created_by_field()
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by = updated_by_field()

    class Meta:
        verbose_name = _("manufacturer")
        verbose_name_plural = _("manufacturers")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="manufacturer_unique_name"),
            *stars_range_constraints("manufacturer", MANUFACTURER_RATINGS),
        ]

    def __str__(self):
        return self.name

    @property
    def remarketing_average(self):
        return average_stars(getattr(self, field) for field in MANUFACTURER_RATINGS)


class PhotoKind(models.TextChoices):
    """Kinds of photo of an inspection report; an asset class says which ones are required."""

    FRONT = "front", _("Front")
    BACK = "back", _("Back")
    SIDE = "side", _("Side")
    SCREEN = "screen", _("Screen")
    DAMAGE = "damage", _("Damage")
    SERIAL = "serial", _("Serial Number")
    OTHER = "other", _("Other")


class AssetClass(models.Model):
    """A kind of leased asset within a sub-vertical (e.g. Industry / Yellow line / Excavators).

    The name is unique within its sub-vertical. The remarketing rating — how the class performs
    in the used-equipment market — is made of four 0–5 star ratings:

    - liquidity: how easily it sells used (0 no demand, 5 sells easily);
    - value_retention: how well it keeps its value over time (0 loses a lot, 5 keeps it well);
    - technology_renewal: how fast its technology renews (0 rarely, 5 very fast);
    - usage_breadth: how broad its use and applications are (0 very narrow, 5 very broad).
    """

    # In English (the default language)
    name = models.CharField(_("name"), max_length=100)
    plural_name = models.CharField(_("plural name"), max_length=100)
    # The name and plural in other languages, optional ({"pt-br": {"name", "plural"}, ...};
    # empty: English). See catalogs/names.py.
    translations = models.JSONField(_("translations"), default=dict, blank=True)
    icon = models.CharField(_("icon"), max_length=60, default=DEFAULT_ASSET_ICON)
    sub_vertical = models.ForeignKey(
        SubVertical,
        on_delete=models.PROTECT,  # a sub-vertical (or vertical) with asset classes stays
        related_name="asset_classes",
        verbose_name=_("sub-vertical"),
    )
    liquidity = star_rating_field(_("liquidity"))
    value_retention = star_rating_field(_("value retention"))
    technology_renewal = star_rating_field(_("technology renewal"))
    usage_breadth = star_rating_field(_("usage breadth"))
    # Words used to relate assets to this class (lowercase, no duplicates)
    keywords = keywords_field()
    notes = models.TextField(_("notes"), blank=True)
    # Specification fields every priced asset of this class describes (see catalogs/specs.py)
    spec_template = models.JSONField(_("specification template"), default=list, blank=True)
    # Photos every inspection report of an asset of this class must have (PhotoKind values)
    required_photo_kinds = ArrayField(
        models.CharField(max_length=10, choices=PhotoKind.choices),
        default=list,
        blank=True,
        verbose_name=_("required photos"),
    )
    is_enabled = models.BooleanField(_("enabled"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    created_by = created_by_field()
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by = updated_by_field()

    class Meta:
        verbose_name = _("asset class")
        verbose_name_plural = _("asset classes")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "sub_vertical", Lower("name"), name="asset_class_unique_name_per_sub_vertical"
            ),
            *stars_range_constraints("asset_class", REMARKETING_RATINGS),
        ]

    def __str__(self):
        return f"{self.sub_vertical} / {self.name}"

    @property
    def remarketing_average(self):
        return average_stars(getattr(self, field) for field in REMARKETING_RATINGS)


class Tracking(models.TextChoices):
    """How the inventory controls a model: each unit with its Horizon ID, or a balance of
    low-value accessories (cables, chargers) by quantity."""

    UNIT = "unit", _("By Unit")
    QUANTITY = "quantity", _("By Quantity")


class AssetModel(models.Model):
    """A manufacturer's model of an asset class (e.g. Dell Latitude 5440, a notebook), described
    by the class's specification template. Inventory assets are units of a model; each keeps its
    own specification values, starting with the model's.

    Inspection uses its kit checklist (items expected with each unit) and test script (checks
    to run); `has_storage` asks for a certified data erasure; `serial_regex` checks serials
    read at triage.
    """

    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.PROTECT,
        related_name="asset_models",
        verbose_name=_("manufacturer"),
    )
    name = models.CharField(_("model"), max_length=150)
    asset_class = models.ForeignKey(
        AssetClass,
        on_delete=models.PROTECT,
        related_name="asset_models",
        verbose_name=_("asset class"),
    )
    # Values of the asset class's template (catalogs.specs.snapshot_values)
    specs = models.JSONField(_("specifications"), default=list, blank=True)
    tracking = models.CharField(
        _("tracking"), max_length=10, choices=Tracking.choices, default=Tracking.UNIT
    )
    serial_regex = models.CharField(_("serial number pattern"), max_length=200, blank=True)
    # Items expected with each unit: [{"item": "Charger", "essential": false}, …] — a missing
    # essential item makes the unit incomplete (I), a missing accessory partial (P)
    kit_checklist = models.JSONField(_("kit checklist"), default=list, blank=True)
    test_script = models.JSONField(_("test script"), default=list, blank=True)
    has_storage = models.BooleanField(_("has data storage"), default=False)
    keywords = keywords_field()
    notes = models.TextField(_("notes"), blank=True)
    is_enabled = models.BooleanField(_("enabled"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    created_by = created_by_field()
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by = updated_by_field()

    class Meta:
        verbose_name = _("asset model")
        verbose_name_plural = _("asset models")
        ordering = ["manufacturer__name", "name"]
        constraints = [
            models.UniqueConstraint(
                "manufacturer", Lower("name"), name="asset_model_unique_name_per_manufacturer"
            ),
        ]

    def __str__(self):
        return f"{self.manufacturer.name} {self.name}"
