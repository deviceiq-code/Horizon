"""eFMV analyses (estimated Fair Market Value): for a customer, its account manager and a
business vertical (or one of its sub-verticals) — the premises, set when the analysis is
created (wizard) and not changed afterwards — one or more scenarios, each with a term, a scope
and the assets (from Average Prices, with quantities) that are evaluated. Scenarios are edited
freely.

An item follows the asset's *current* average price: it stores the price's lineage (shared by
all its versions), so a new version applies at once.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

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
    # The assets it admits: the vertical's (any sub-vertical) or, when a sub-vertical is chosen,
    # only that sub-vertical's. Required by the API (null only for analyses whose scenarios had
    # none before the vertical moved to the analysis).
    vertical = models.ForeignKey(
        "catalogs.Vertical",
        on_delete=models.PROTECT,
        null=True,
        related_name="efmv_analyses",
        verbose_name=_("vertical"),
    )
    sub_vertical = models.ForeignKey(
        "catalogs.SubVertical",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="efmv_analyses",
        verbose_name=_("sub-vertical"),
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
    # Who saved it last (its creator until someone saves it)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="+",
        verbose_name=_("updated by"),
    )

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

    def admits(self, sub_vertical) -> bool:
        """Whether an asset of this sub-vertical can be in the analysis's scenarios."""
        return in_scope(self.vertical_id, self.sub_vertical_id, sub_vertical)


def format_code(year: int, sequence: int) -> str:
    return f"EFMV-{year}-{sequence:04d}"


class EfmvScenario(models.Model):
    analysis = models.ForeignKey(
        EfmvAnalysis, on_delete=models.CASCADE, related_name="scenarios", verbose_name=_("analysis")
    )
    # Optional: the scenario is called by its term and this name (`title`)
    name = models.CharField(_("name"), max_length=100, blank=True)
    term_months = models.PositiveSmallIntegerField(
        _("term (months)"), validators=[MinValueValidator(1), MaxValueValidator(MAX_TERM_MONTHS)]
    )
    # Short explanation of the assets of the scenario
    scope = models.TextField(_("scope"), blank=True)
    position = models.PositiveSmallIntegerField(_("position"), default=0)

    class Meta:
        verbose_name = _("scenario")
        verbose_name_plural = _("scenarios")
        # By official name: the term (as a number), then the name ("12 Months", "36 Months",
        # "36 Months - Desktops", "120 Months")
        ordering = ["term_months", Lower("name"), "id"]
        constraints = [
            # Unique official name (`title`): term + name
            models.UniqueConstraint(
                "analysis", "term_months", Lower("name"), name="efmv_scenario_unique_title"
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def title(self) -> str:
        return scenario_title(self.term_months, self.name)


def scenario_title(term_months: int, name: str) -> str:
    """The official name of a scenario: its term and the name given, if any ("36 Months -
    Desktops", "60 Months"), in the active language."""
    months = ngettext("%(count)d Month", "%(count)d Months", term_months) % {"count": term_months}
    return f"{months} - {name}" if name else months


def title_key(term_months: int, name: str) -> tuple[int, str]:
    """What makes two scenarios' official names equal (the name ignores case)."""
    return term_months, name.casefold()


def in_scope(vertical_id, sub_vertical_id, sub_vertical) -> bool:
    """An asset (by its sub-vertical) fits an analysis's vertical / sub-vertical."""
    if vertical_id is None:
        return True
    if sub_vertical_id is not None:
        return sub_vertical.pk == sub_vertical_id
    return sub_vertical.vertical_id == vertical_id


class ServiceMode(models.TextChoices):
    """How a service's value relates to its asset's: on top of it, or part of it."""

    ADD = "add", _("Added to the asset")
    DEDUCT = "deduct", _("Deducted from the asset")


class EfmvScenarioItem(models.Model):
    """An asset of a scenario: an average price (any of its versions; the current one counts)
    and how many. The same asset may be in several rows of a scenario (e.g. its value differs
    by the state where it is delivered: freight and taxes)."""

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
    # Value of one unit at the end of the term, typed by the analyst — negative when disposing
    # of it costs more than it is worth; null = the average
    # price's curve at the scenario's term (follows the term and the price's current version)
    efmv_value = models.DecimalField(
        _("eFMV value"),
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    # Its service (SV), at most one, shown as a row under it: e.g. a warranty. Per unit (the
    # item's quantity); added to the asset's value or deducted from it (the asset is then worth
    # less, and positioned so); eFMV 0 (services are not resold). No name = no service.
    service_name = models.CharField(_("service"), max_length=100, blank=True)
    service_value = models.DecimalField(
        _("service value"),
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    service_mode = models.CharField(
        _("service mode"), max_length=10, choices=ServiceMode, default=ServiceMode.ADD
    )
    position = models.PositiveSmallIntegerField(_("position"), default=0)

    class Meta:
        verbose_name = _("scenario asset")
        verbose_name_plural = _("scenario assets")
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.scenario} × {self.quantity}"
