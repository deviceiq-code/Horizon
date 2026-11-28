from django.apps import AppConfig


class RemarketingConfig(AppConfig):
    """Remarketing (an app of the suite): the sale of used assets — offers, buyers, sales and
    sales channels. A skeleton: no models yet (the business rules are being defined). The
    inventory, formerly this app, is Asset Management (`inventory/`)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "remarketing"
