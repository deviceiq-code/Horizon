from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "tax_id",
        "city",
        "state",
        "primary_account_manager",
        "is_active",
    ]
    list_filter = ["is_active", "country", "state"]
    search_fields = ["name", "trade_name", "tax_id", "email", "city"]
    autocomplete_fields = ["primary_account_manager", "secondary_account_managers"]
    readonly_fields = ["created_at", "updated_at"]
