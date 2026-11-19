from django.contrib import admin

from .models import AveragePrice, PriceDocument, PricePoint


class PricePointInline(admin.TabularInline):
    model = PricePoint
    extra = 0
    can_delete = False
    readonly_fields = ["term_months", "mode", "amount", "value"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AveragePrice)
class AveragePriceAdmin(admin.ModelAdmin):
    """Read-only: rows are created in the app (each change is a new version)."""

    list_display = [
        "id",
        "asset_class",
        "manufacturer",
        "model",
        "original_value",
        "is_current",
        "deleted_at",
        "created_at",
    ]
    list_filter = ["is_current", "currency", "sub_vertical__vertical"]
    search_fields = ["model", "description", "asset_class__name", "manufacturer__name"]
    inlines = [PricePointInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PriceDocument)
class PriceDocumentAdmin(admin.ModelAdmin):
    """Read-only: documents are added and removed in the app."""

    list_display = ["id", "name", "size", "content_type", "lineage", "uploaded_at", "uploaded_by"]
    search_fields = ["name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
