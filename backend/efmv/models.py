"""eFMV analyses (estimated Fair Market Value): for a customer and its account manager, one or
more scenarios, each with a term, a scope and the assets (from Average Prices, with
quantities) that are evaluated. Analyses are edited freely.

An item follows the asset's *current* average price: it stores the price's lineage (shared by
all its versions), so a new version applies at once.
"""

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


class EfmvScenarioItem(models.Model):
    """An asset of a scenario: an average price (any of its versions; the current one counts)
    and how many."""

    scenario = models.ForeignKey(
        EfmvScenario, on_delete=models.CASCADE, related_name="items", verbose_name=_("scenario")
    )
    # AveragePrice.lineage: the current version is always used
    price_lineage = models.UUIDField(_("average price"), db_index=True)
    quantity = models.PositiveIntegerField(_("quantity"), validators=[MinValueValidator(1)])
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
