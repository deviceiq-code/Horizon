from django.contrib import admin

from .models import ServiceProvider


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    """The Service Provider role; the entity's data is in Business Entities."""

    list_display = ["id", "entity", "is_active"]
    list_filter = ["is_active", "entity__country", "entity__state"]
    search_fields = ["entity__name", "entity__trade_name", "entity__tax_id", "entity__city"]
    autocomplete_fields = ["entity"]
    readonly_fields = ["created_at", "updated_at"]
