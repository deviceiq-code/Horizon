"""Reference data ("catalogs"): small tables used across the system, e.g. business verticals."""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Lower
from django.utils import translation
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from account_managers.models import AccountManager


class Vertical(models.Model):
    """A business vertical (industry segment) and the account managers who may work in it.

    Account managers, the enabled flag and notes apply to all of its sub-verticals.
    """

    name = models.CharField(_("name"), max_length=100)
    account_managers = models.ManyToManyField(
        AccountManager,
        blank=True,
        related_name="verticals",
        verbose_name=_("account managers"),
    )
    is_enabled = models.BooleanField(_("enabled"), default=True)
    notes = models.TextField(_("notes"), blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

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
