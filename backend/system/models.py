"""The system app keeps no user settings (every one is the user's own: accounts.UserPreferences).
It holds the internet helpers (system.web: SearXNG image search and safe image download) and
their messages (system.messages), and the **word dictionary** shared by everyone: words that,
typed in a form (whole words, any case), become the dictionary's spelling ("ltda" → "LTDA",
"s/a" → "S/A") — the Word Dictionary Smart Tool, applied by the browser when a field is left."""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

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
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("dictionary word")
        verbose_name_plural = _("dictionary words")
        ordering = [Lower("replacement")]
        constraints = [
            models.UniqueConstraint(Lower("replacement"), name="dictionary_unique_replacement"),
        ]

    def __str__(self):
        return self.replacement
