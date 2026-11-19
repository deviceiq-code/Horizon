from django.contrib import admin

from .models import SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ["searxng_url", "updated_at", "updated_by"]
    readonly_fields = ["updated_at", "updated_by"]
