from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """The Customer role; the entity's data is in Business Entities."""

    list_display = ["id", "entity", "primary_account_manager", "is_active"]
    list_filter = ["is_active", "entity__country", "entity__state"]
    search_fields = ["entity__name", "entity__trade_name", "entity__tax_id", "entity__city"]
    autocomplete_fields = ["entity", "primary_account_manager", "secondary_account_managers"]
    readonly_fields = ["created_at", "updated_at"]
