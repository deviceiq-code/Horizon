from django.apps import AppConfig


class PartnersConfig(AppConfig):
    """Services and Partnerships (an app of the suite): the services
    Horizon offers, partners, incentive programs, discounts and fees. A skeleton: no models yet
    (the business rules are being defined)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "partners"
