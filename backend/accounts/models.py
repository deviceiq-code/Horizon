from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Theme(models.TextChoices):
    LIGHT = "light", _("Light")
    DARK = "dark", _("Dark")
    SYSTEM = "system", _("Follow system")


class ColorTheme(models.TextChoices):
    """Color schemes of the interface (each one has a light and a dark version, picked by
    `theme`). Names are proper names: not translated."""

    METALLIC_FOUNDATIONS = "metallic_foundations", "Metallic Foundations"
    EARTHY_SERENE = "earthy_serene", "Earthy and Serene"
    SLEEK_FUTURISTIC = "sleek_futuristic", "Sleek and Futuristic"


class UiScale(models.TextChoices):
    """Size of the interface (text, spacing, fields). "auto" follows the width of the browser
    window: smaller on notebooks, larger on wide screens."""

    AUTO = "auto", _("Automatic")
    SMALL = "small", _("Small")
    NORMAL = "normal", _("Normal")
    LARGE = "large", _("Large")


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
    color_theme = models.CharField(
        _("color theme"),
        max_length=40,
        choices=ColorTheme,
        default=ColorTheme.METALLIC_FOUNDATIONS,
    )
    ui_scale = models.CharField(
        _("interface size"), max_length=10, choices=UiScale, default=UiScale.AUTO
    )
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
