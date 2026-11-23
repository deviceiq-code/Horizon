from django.contrib import admin

from .models import ServiceProvider


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "tax_id", "city", "state", "is_active"]
    list_filter = ["is_active", "country", "state"]
    search_fields = ["name", "trade_name", "tax_id", "email", "city"]
    readonly_fields = ["created_at", "updated_at"]
