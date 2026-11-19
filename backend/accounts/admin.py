from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import UserPreferences


class UserPreferencesInline(admin.StackedInline):
    model = UserPreferences
    can_delete = False
    readonly_fields = ["updated_at"]


User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserPreferencesInline]
