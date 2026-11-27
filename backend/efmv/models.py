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
from config.keywords import keywords_field


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
    # Not premises: they can change after creation
    keywords = keywords_field()
    # Where it comes from elsewhere — e.g. the opportunity's number in a CRM
    external_reference = models.CharField(_("external reference"), max_length=100, blank=True)
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
    """How an attached item's value relates to its hardware's: on top of it, or part of it."""

    ADD = "add", _("Added to the asset")
    DEDUCT = "deduct", _("Deducted from the asset")


class ItemKind(models.TextChoices):
    """Hardware (an average price), software or a service."""

    HW = "hw", _("Hardware")
    SW = "sw", _("Software")
    SV = "sv", _("Service")


class EfmvScenarioItem(models.Model):
    """A line of a scenario: hardware (an average price — any of its versions; the current one
    counts — and how many), or software / a service on its own (a description, how many, a
    value). Software and services may also be attached to a hardware line (at most one of each),
    shown under it: per unit of the hardware (its quantity), added to its value or deducted from
    it. The same asset may be in several lines (e.g. its value differs by the state where it is
    delivered: freight and taxes). Services are worth nothing at the end of the term (eFMV 0);
    software starts at 0 and may be typed."""

    scenario = models.ForeignKey(
        EfmvScenario, on_delete=models.CASCADE, related_name="items", verbose_name=_("scenario")
    )
    kind = models.CharField(_("kind"), max_length=2, choices=ItemKind, default=ItemKind.HW)
    # Hardware: AveragePrice.lineage (the current version is always used); none otherwise
    price_lineage = models.UUIDField(_("average price"), db_index=True, null=True, blank=True)
    # Software / service: what it is (empty: shown as "Software" / "Service")
    description = models.CharField(_("description"), max_length=100, blank=True)
    # Attached to a hardware line of the same scenario (software or service), or on its own
    attached_to = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
        verbose_name=_("attached to"),
    )
    # Attached only: added to the hardware's value or deducted from it
    mode = models.CharField(_("mode"), max_length=10, choices=ServiceMode, default=ServiceMode.ADD)
    quantity = models.PositiveIntegerField(_("quantity"), validators=[MinValueValidator(1)])
    # Typed by the analyst (hardware: never taken from Average Prices, only compared with it);
    # attached: per unit of the hardware
    unit_value = models.DecimalField(
        _("unit value"),
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    # Value of one unit at the end of the term, typed by the analyst — negative when disposing
    # of it costs more than it is worth. Hardware: null = the average price's curve at the
    # scenario's term (follows the term and the price's current version). Software: null = 0.
    # Services: always 0.
    efmv_value = models.DecimalField(
        _("eFMV value"),
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    position = models.PositiveSmallIntegerField(_("position"), default=0)

    class Meta:
        verbose_name = _("scenario asset")
        verbose_name_plural = _("scenario assets")
        ordering = ["position", "id"]
        constraints = [
            # A hardware line has at most one software and one service attached
            models.UniqueConstraint(
                fields=["attached_to", "kind"],
                condition=models.Q(attached_to__isnull=False),
                name="efmv_item_one_attachment_per_kind",
            ),
            models.CheckConstraint(
                condition=models.Q(kind="hw", price_lineage__isnull=False)
                | (~models.Q(kind="hw") & models.Q(price_lineage__isnull=True)),
                name="efmv_item_price_only_for_hardware",
            ),
        ]

    def __str__(self):
        return f"{self.scenario} × {self.quantity}"
