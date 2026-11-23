"""System-wide settings, edited by administrators in the app (Settings page)."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SystemSettings(models.Model):
    """A single row (pk=1). Read it with SystemSettings.current()."""

    # SearXNG instance used to search photos on the internet (JSON output must be enabled
    # there). Empty = photo search off.
    searxng_url = models.URLField(_("SearXNG URL"), max_length=300, blank=True)

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
        verbose_name = _("system settings")
        verbose_name_plural = _("system settings")

    def __str__(self):
        return str(_("System settings"))

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def current(cls) -> "SystemSettings":
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj
