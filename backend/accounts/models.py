from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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
    EMERALD_SLATE = "emerald_slate", "Emerald Slate"


class UiScale(models.TextChoices):
    """Size of the interface (text, spacing, fields). "auto" follows the width of the browser
    window: smaller on notebooks, larger on wide screens."""

    AUTO = "auto", _("Automatic")
    SMALL = "small", _("Small")
    NORMAL = "normal", _("Normal")
    LARGE = "large", _("Large")


class DateFormat(models.TextChoices):
    """How dates are written. "auto": as usual in the interface's language."""

    AUTO = "auto", _("Automatic")
    DMY = "dmy", "DD/MM/YYYY"
    MDY = "mdy", "MM/DD/YYYY"
    YMD = "ymd", "YYYY-MM-DD"


class TimeFormat(models.TextChoices):
    """How times are written. "auto": as usual in the interface's language."""

    AUTO = "auto", _("Automatic")
    H24 = "24h", _("24 hours")
    H12 = "12h", _("12 hours (AM/PM)")


class NumberFormat(models.TextChoices):
    """How numbers are written (thousands and decimal separators). "auto": as usual in the
    interface's language."""

    AUTO = "auto", _("Automatic")
    DOT_COMMA = "dot_comma", "1.234,56"
    COMMA_DOT = "comma_dot", "1,234.56"
    SPACE_COMMA = "space_comma", "1 234,56"


class CurrencyDisplay(models.TextChoices):
    """How the currency of money values is shown — always, on the left of value fields (values
    keep their own currency)."""

    SYMBOL = "symbol", _("Symbol (R$)")
    CODE = "code", _("Code (BRL)")


# The currencies a user can choose as theirs (ISO 4217); names, symbols in the interface
CURRENCIES = [
    "BRL", "USD", "EUR", "GBP", "JPY", "CNY", "CHF", "CAD", "AUD", "MXN",
    "ARS", "CLP", "COP", "PEN", "UYU", "PYG", "BOB", "INR", "ZAR",
]  # fmt: skip


class WebSearchEngine(models.TextChoices):
    """Where "Search the Internet" (beside some text fields) opens: a page cannot use the
    browser's default search engine, so the user picks one."""

    GOOGLE = "google", "Google"
    BING = "bing", "Bing"
    DUCKDUCKGO = "duckduckgo", "DuckDuckGo"
    ECOSIA = "ecosia", "Ecosia"
    BRAVE = "brave", "Brave Search"
    YAHOO = "yahoo", "Yahoo"


MAX_UI_STATE_BYTES = 20_000


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
    date_format = models.CharField(
        _("date format"), max_length=10, choices=DateFormat, default=DateFormat.AUTO
    )
    time_format = models.CharField(
        _("time format"), max_length=10, choices=TimeFormat, default=TimeFormat.AUTO
    )
    number_format = models.CharField(
        _("number format"), max_length=12, choices=NumberFormat, default=NumberFormat.AUTO
    )
    # Decimal places of percentages everywhere (1–5)
    percent_places = models.PositiveSmallIntegerField(
        _("percentage decimal places"),
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    # The user's currency (its symbol and code come from it); values keep their own currency
    currency = models.CharField(
        _("currency"), max_length=3, choices=[(c, c) for c in CURRENCIES], default="BRL"
    )
    currency_display = models.CharField(
        _("currency display"),
        max_length=10,
        choices=CurrencyDisplay,
        default=CurrencyDisplay.SYMBOL,
    )
    # How the user left the interface, kept with the account so it follows them to any
    # computer: e.g. {"sideMenu": {"wide": "open"}, "filters": {"customers": true}}
    ui_state = models.JSONField(_("interface state"), default=dict, blank=True)
    web_search_engine = models.CharField(
        _("web search engine"),
        max_length=12,
        choices=WebSearchEngine,
        default=WebSearchEngine.GOOGLE,
    )
    # Smart Tools (conveniences of the interface)
    # Entering a text field selects its content (typing replaces it)
    select_on_focus = models.BooleanField(_("select on focus"), default=True)
    # eFMV scenarios: the scope written from their assets while it is not written by hand
    auto_scope = models.BooleanField(_("automatic scope"), default=True)
    # …leaving out the groups of assets under this % of the units
    scope_threshold = models.DecimalField(
        _("negligible below (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("5"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
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
