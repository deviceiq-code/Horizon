from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Theme(models.TextChoices):
    LIGHT = "light", _("Light")
    DARK = "dark", _("Dark")
    SYSTEM = "system", _("Follow system")


class UserPreferences(models.Model):
    """Settings each user picks on the settings page."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
        verbose_name=_("user"),
    )
    language = models.CharField(
        _("language"),
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
    )
    theme = models.CharField(_("theme"), max_length=10, choices=Theme, default=Theme.SYSTEM)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("user preferences")
        verbose_name_plural = _("user preferences")

    def __str__(self):
        return str(self.user)

    @classmethod
    def for_user(cls, user):
        """Return the user's preferences, creating them with default values if needed."""
        preferences, _created = cls.objects.get_or_create(user=user)
        return preferences
