from django.contrib import admin

from .models import AccountManager


@admin.register(AccountManager)
class AccountManagerAdmin(admin.ModelAdmin):
    list_display = ["id", "full_name", "email", "updated_at"]
    search_fields = ["full_name", "email"]
    filter_horizontal = ["verticals"]
    readonly_fields = ["created_at", "updated_at"]
