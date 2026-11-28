from django.contrib import admin

from .models import BusinessEntity, Buyer, Supplier


@admin.register(BusinessEntity)
class BusinessEntityAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "trade_name", "tax_id", "country", "city", "state", "is_active"]
    list_filter = ["is_active", "country", "state"]
    search_fields = ["name", "trade_name", "tax_id", "email", "city"]
    autocomplete_fields = ["parent"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Supplier, Buyer)
class EntityRoleAdmin(admin.ModelAdmin):
    list_display = ["id", "entity", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["entity__name", "entity__trade_name", "entity__tax_id"]
    autocomplete_fields = ["entity"]
    readonly_fields = ["created_at", "updated_at"]
