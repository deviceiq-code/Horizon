"""The system app keeps no user settings (every one is the user's own: accounts.UserPreferences).
It holds the internet helpers (system.web: SearXNG image search and safe image download) and
their messages (system.messages), and the **word dictionary** shared by everyone: words that,
typed in a form (whole words, any case), become the dictionary's spelling ("ltda" → "LTDA",
"s/a" → "S/A") — the Word Dictionary Smart Tool, applied by the browser when a field is left."""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from config.audit import created_by_field, updated_by_field

MAX_WORD = 60
MAX_VARIANTS = 30


class DictionaryWord(models.Model):
    """A spelling and the ways it may be typed. The spelling itself, in any case, is also
    replaced ("Ltda" → "LTDA")."""

    replacement = models.CharField(_("replacement"), max_length=MAX_WORD)
    # Other ways to type it (any case): "sa.", "s.a."
    variants = ArrayField(
        models.CharField(max_length=MAX_WORD), verbose_name=_("variants"), default=list, blank=True
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, null=True)
    created_by = created_by_field()
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by = updated_by_field()

    class Meta:
        verbose_name = _("dictionary word")
        verbose_name_plural = _("dictionary words")
        ordering = [Lower("replacement")]
        constraints = [
            models.UniqueConstraint(Lower("replacement"), name="dictionary_unique_replacement"),
        ]

    def __str__(self):
        return self.replacement


class Release(models.Model):
    """A version of Horizon and what it brought, shown to everyone in the Home's journal. Each
    change delivered adds one (a data migration, so every environment gets the same), raising
    only the last number (1.0.0 → 1.0.1). Notes are written for the users, per language:
    {"en": ["…", …], "pt-br": […], "es": […]}."""

    version = models.CharField(_("version"), max_length=20, unique=True)
    released_on = models.DateField(_("released on"))
    notes = models.JSONField(_("notes"), default=dict)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("release")
        verbose_name_plural = _("releases")
        ordering = ["-released_on", "-id"]

    def __str__(self):
        return self.version

    @property
    def number(self) -> tuple[int, ...]:
        """The version as numbers, to compare (1.0.10 after 1.0.9)."""
        return tuple(int(part) for part in self.version.split(".") if part.isdigit())
