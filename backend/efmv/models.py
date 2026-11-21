"""eFMV analyses (estimated Fair Market Value): for a customer and its account manager, one or
more scenarios, each with a term, a scope and the assets (from Average Prices, with
quantities) that are evaluated. Analyses are edited freely.

An item follows the asset's *current* average price: it stores the price's lineage (shared by
all its versions), so a new version applies at once.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from catalogs.models import MAX_TERM_MONTHS


class EfmvAnalysis(models.Model):
    # Readable unique code: EFMV-<year>-<sequence of the year, 4 digits>
    year = models.PositiveSmallIntegerField(_("year"))
    sequence = models.PositiveIntegerField(_("sequence"))
    account_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="efmv_analyses",
        verbose_name=_("account manager"),
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="efmv_analyses",
        verbose_name=_("customer"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("eFMV analysis")
        verbose_name_plural = _("eFMV analyses")
        ordering = ["-year", "-sequence"]
        constraints = [
            models.UniqueConstraint(fields=["year", "sequence"], name="efmv_unique_code"),
        ]

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        return format_code(self.year, self.sequence)


def format_code(year: int, sequence: int) -> str:
    return f"EFMV-{year}-{sequence:04d}"


class EfmvScenario(models.Model):
    analysis = models.ForeignKey(
        EfmvAnalysis, on_delete=models.CASCADE, related_name="scenarios", verbose_name=_("analysis")
    )
    name = models.CharField(_("name"), max_length=100)
    term_months = models.PositiveSmallIntegerField(
        _("term (months)"), validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_MONTHS)]
    )
    # Short explanation of the assets of the scenario
    scope = models.TextField(_("scope"), blank=True)
    # Which assets can be in it: those of the vertical (any sub-vertical) or, when a
    # sub-vertical is chosen, only those of that sub-vertical. Required by the API (null only
    # for scenarios saved before it existed).
    vertical = models.ForeignKey(
        "catalogs.Vertical",
        on_delete=models.PROTECT,
        null=True,
        related_name="efmv_scenarios",
        verbose_name=_("vertical"),
    )
    sub_vertical = models.ForeignKey(
        "catalogs.SubVertical",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="efmv_scenarios",
        verbose_name=_("sub-vertical"),
    )
    position = models.PositiveSmallIntegerField(_("position"), default=0)

    class Meta:
        verbose_name = _("scenario")
        verbose_name_plural = _("scenarios")
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint("analysis", Lower("name"), name="efmv_scenario_unique_name"),
        ]

    def __str__(self):
        return self.name

    def admits(self, sub_vertical) -> bool:
        """Whether an asset of this sub-vertical can be in the scenario."""
        return in_scope(self.vertical_id, self.sub_vertical_id, sub_vertical)


def in_scope(vertical_id, sub_vertical_id, sub_vertical) -> bool:
    """An asset (by its sub-vertical) fits a scenario's vertical / sub-vertical."""
    if vertical_id is None:
        return True
    if sub_vertical_id is not None:
        return sub_vertical.pk == sub_vertical_id
    return sub_vertical.vertical_id == vertical_id


class EfmvScenarioItem(models.Model):
    """An asset of a scenario: an average price (any of its versions; the current one counts)
    and how many."""

    scenario = models.ForeignKey(
        EfmvScenario, on_delete=models.CASCADE, related_name="items", verbose_name=_("scenario")
    )
    # AveragePrice.lineage: the current version is always used
    price_lineage = models.UUIDField(_("average price"), db_index=True)
    quantity = models.PositiveIntegerField(_("quantity"), validators=[MinValueValidator(1)])
    # Typed by the analyst (never taken from Average Prices, only compared with it)
    unit_value = models.DecimalField(
        _("unit value"),
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    # Value of one unit at the end of the term, typed by the analyst; null = the average
    # price's curve at the scenario's term (follows the term and the price's current version)
    efmv_value = models.DecimalField(
        _("eFMV value"),
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    position = models.PositiveSmallIntegerField(_("position"), default=0)

    class Meta:
        verbose_name = _("scenario asset")
        verbose_name_plural = _("scenario assets")
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["scenario", "price_lineage"], name="efmv_item_unique_price"
            ),
        ]

    def __str__(self):
        return f"{self.scenario} × {self.quantity}"
