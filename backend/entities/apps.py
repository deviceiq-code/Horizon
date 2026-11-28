from django.apps import AppConfig


class EntitiesConfig(AppConfig):
    """Business Entities: every company or person Horizon deals with, and their roles
    (customer, supplier, service provider, buyer). docs/business-entities.md."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "entities"
