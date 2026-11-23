from django.contrib import admin

from .models import Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "ownership", "service_provider", "city", "state", "is_active"]
    list_filter = ["ownership", "is_active", "state"]
    search_fields = ["name", "city", "contact_name"]
    readonly_fields = ["created_at", "updated_at"]
