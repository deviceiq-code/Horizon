from django.contrib import admin

from .models import DictionaryWord, Release


@admin.register(DictionaryWord)
class DictionaryWordAdmin(admin.ModelAdmin):
    list_display = ["replacement", "variants", "updated_at"]
    search_fields = ["replacement"]


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    """Versions are added by data migrations (every environment the same); fixed here when
    needed."""

    list_display = ["version", "released_on", "created_at"]
    readonly_fields = ["created_at"]
