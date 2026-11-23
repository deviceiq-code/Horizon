"""Average prices: market value estimates of assets over time (12, 24, 36… months).

Rows are immutable records. "Editing" creates a new row (a new version, with a new creation
date) that supersedes the previous one, so past values stay available. A single version can be
erased from the history; deleting the whole row only hides it. The current version is always the
newest one not deleted. Each row keeps a snapshot of what it was based on (terms of the
sub-vertical, specification template of the asset class), so later changes to catalogs
never alter history.
"""

import posixpath
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalogs.models import AssetClass, Manufacturer, SubVertical
from config.keywords import keywords_field

from .curves import increasing_terms, monthly_curve, percent_of
from .positioning import PositionLimits


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
    description = models.TextField(_("description"), blank=True)
    # Kept by each version (a new version starts with the previous one's)
    keywords = keywords_field()
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
    # Shared by every version of the row (documents belong to it, not to one version)
    lineage = models.UUIDField(_("lineage"), default=uuid.uuid4, editable=False, db_index=True)

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

    def delete_version(self) -> None:
        """Erase this version for good (with its values). The versions around it are linked
        together and the newest one left becomes the current one; erasing the only version
        erases the row."""
        with transaction.atomic():
            chain = self._lock_chain()
            mine = next(row for row in chain if row.pk == self.pk)
            newer = next((row for row in chain if row.supersedes_id == self.pk), None)
            if newer is not None:
                # One-to-one link: detach first, then link the newer one to the older one
                older_id = mine.supersedes_id
                mine.supersedes = None
                mine.save(update_fields=["supersedes"])
                newer.supersedes_id = older_id
                newer.save(update_fields=["supersedes"])
            mine.delete()
            left = [row for row in chain if row is not mine]
            self._update_current(left)
            if not left:
                # Nothing left of the row: its documents go too
                for document in PriceDocument.objects.filter(lineage=self.lineage):
                    document.delete()

    def delete_all_versions(self, user) -> None:
        """Hide every version of the row (kept in the database; it leaves the list)."""
        with transaction.atomic():
            chain = self._lock_chain()
            now = timezone.now()
            for row in chain:
                if row.deleted_at is None:
                    row.deleted_at = now
                    row.deleted_by = user
            AveragePrice.objects.bulk_update(chain, ["deleted_at", "deleted_by"])
            self._update_current(chain)

    def _lock_chain(self) -> list["AveragePrice"]:
        # Lock every version so a new version or another delete cannot interleave
        ids = [version.pk for version in self.versions()]
        return list(AveragePrice.objects.select_for_update().filter(pk__in=ids).order_by("id"))

    @staticmethod
    def _update_current(chain: list["AveragePrice"]) -> None:
        """The current version is always the newest one not deleted."""
        standing = [row for row in chain if row.deleted_at is None]
        newest = max(standing, key=lambda row: (row.created_at, row.pk), default=None)
        for row in chain:
            row.is_current = row is newest
        AveragePrice.objects.bulk_update(chain, ["is_current"])

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


def _document_path(instance: "PriceDocument", filename: str) -> str:
    # Random stored name (the original one is kept in `name`), one folder per row
    ext = posixpath.splitext(filename)[1].lower()
    return f"price-documents/{instance.lineage}/{uuid.uuid4().hex}{ext}"


class PriceDocument(models.Model):
    """A file about the priced asset (catalog, brochure, spec sheet…) or its photo, shared by
    every version of the row. Deleting it also removes the stored file."""

    lineage = models.UUIDField(_("lineage"), db_index=True)
    file = models.FileField(_("file"), upload_to=_document_path, max_length=255)
    name = models.CharField(_("name"), max_length=255)
    size = models.PositiveBigIntegerField(_("size (bytes)"))
    content_type = models.CharField(_("content type"), max_length=100)
    # The photo of the asset (at most one per row) instead of a document
    is_photo = models.BooleanField(_("photo"), default=False)
    # Where it came from, when downloaded from the internet (page it was found on, or the image)
    source_url = models.URLField(_("source"), max_length=1000, blank=True)
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="+",
        verbose_name=_("uploaded by"),
    )

    class Meta:
        verbose_name = _("document")
        verbose_name_plural = _("documents")
        ordering = ["-uploaded_at", "-id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        storage, path = self.file.storage, self.file.name
        result = super().delete(*args, **kwargs)
        # Remove the file only once the deletion is committed
        transaction.on_commit(lambda: storage.delete(path))
        return result


class PricingSettings(models.Model):
    """Pricing control panel (a single row, pk=1; read it with PricingSettings.current()).

    How a price typed in an analysis is placed against Average Prices (percentages of the
    reference value): at most `compatible_percent` away = compatible; `below_percent` or more
    below = below the historical value; `above_percent` or more above = above it; in between =
    slightly below/above. And how long an average price stays current (`validity_months`,
    from the date of its current version) and whether older ones can still be used.
    """

    compatible_percent = models.DecimalField(
        _("compatible up to (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    below_percent = models.DecimalField(
        _("below from (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    above_percent = models.DecimalField(
        _("above from (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    validity_months = models.PositiveSmallIntegerField(
        _("validity (months)"), default=12, validators=[MinValueValidator(1)]
    )
    accept_expired = models.BooleanField(_("accept expired prices"), default=True)

    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("updated by"),
    )

    class Meta:
        verbose_name = _("pricing settings")
        verbose_name_plural = _("pricing settings")

    def __str__(self):
        return str(_("Pricing settings"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def current(cls) -> "PricingSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def limits(self) -> PositionLimits:
        return PositionLimits(self.compatible_percent, self.below_percent, self.above_percent)
