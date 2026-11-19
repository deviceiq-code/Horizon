"""Average prices: market value estimates of assets over time (12, 24, 36… months).

Rows are immutable records. "Editing" creates a new row (a new version, with a new creation
date) that supersedes the previous one; deleting only hides the row. Nothing is ever lost, so
past values stay available. Each row keeps a snapshot of what it was based on (terms of the
sub-vertical, specification template of the asset class), so later changes to catalogs
never alter history.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from catalogs.models import AssetClass, Manufacturer, SubVertical

from .curves import increasing_terms, monthly_curve, percent_of


class Currency(models.TextChoices):
    # Only BRL for now; more currencies can be added here later
    BRL = "BRL", "BRL"


class AnchorMode(models.TextChoices):
    VALUE = "value", _("Fixed value")
    PERCENT = "percent", _("Percentage of the original value")


class AveragePriceQuerySet(models.QuerySet):
    def active(self):
        """Current version of rows that were not deleted (what the grid shows)."""
        return self.filter(is_current=True, deleted_at__isnull=True)


class AveragePrice(models.Model):
    # What is priced (snapshot at creation; asset class and sub-vertical must match then)
    sub_vertical = models.ForeignKey(
        SubVertical,
        on_delete=models.PROTECT,
        related_name="average_prices",
        verbose_name=_("sub-vertical"),
    )
    asset_class = models.ForeignKey(
        AssetClass,
        on_delete=models.PROTECT,
        related_name="average_prices",
        verbose_name=_("asset class"),
    )
    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.PROTECT,
        related_name="average_prices",
        verbose_name=_("manufacturer"),
    )
    model = models.CharField(_("model"), max_length=150)
    description = models.TextField(_("description"))
    # Values for the asset class's specification template, with the template as it was
    # (see catalogs.specs.snapshot_values)
    specs = models.JSONField(_("specifications"), default=list, blank=True)

    currency = models.CharField(_("currency"), max_length=3, choices=Currency, default=Currency.BRL)
    original_value = models.DecimalField(
        _("original value"),
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    # Versions: a new row supersedes the previous one (which is kept, no longer current)
    supersedes = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by",
        verbose_name=_("previous version"),
    )
    is_current = models.BooleanField(_("current version"), default=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("deleted by"),
    )

    objects = AveragePriceQuerySet.as_manager()

    class Meta:
        verbose_name = _("average price")
        verbose_name_plural = _("average prices")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(original_value__gt=0), name="average_price_positive_value"
            ),
        ]

    def __str__(self):
        return f"{self.manufacturer} {self.model}"

    # --- Curve (computed, never stored) ------------------------------------------------------

    def anchors(self) -> dict[int, Decimal]:
        return {point.term_months: point.value for point in self.points.all()}

    def curve(self):
        return monthly_curve(self.original_value, self.anchors())

    def increasing_terms(self) -> list[int]:
        return increasing_terms(self.original_value, self.anchors())

    def versions(self) -> list["AveragePrice"]:
        """Every version of this row, newest first (including this one)."""
        newest = self
        while True:
            try:
                newest = newest.superseded_by
            except AveragePrice.DoesNotExist:
                break
        chain = []
        row = newest
        while row is not None:
            chain.append(row)
            row = row.supersedes
        return chain


class PricePoint(models.Model):
    """The value of a row at one term, as entered (fixed value or % of the original value)."""

    average_price = models.ForeignKey(AveragePrice, on_delete=models.CASCADE, related_name="points")
    term_months = models.PositiveSmallIntegerField(_("term (months)"))
    mode = models.CharField(_("entered as"), max_length=10, choices=AnchorMode)
    # What the user typed: money (mode "value") or a percentage (mode "percent")
    amount = models.DecimalField(_("amount"), max_digits=14, decimal_places=4)
    # The resulting money value (curves.anchor_value), 2 places
    value = models.DecimalField(_("value"), max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = _("price point")
        verbose_name_plural = _("price points")
        ordering = ["term_months"]
        constraints = [
            models.UniqueConstraint(
                fields=["average_price", "term_months"], name="price_point_unique_term"
            ),
        ]

    def __str__(self):
        return f"{self.term_months} months: {self.value}"

    @property
    def percent(self) -> Decimal:
        return percent_of(self.average_price.original_value, self.value)
