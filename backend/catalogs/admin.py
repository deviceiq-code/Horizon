from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.translation import gettext_lazy as _

from .models import SubVertical, Vertical


class SubVerticalFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            instance = form.instance
            if instance.pk and instance.is_general and self._should_delete_form(form):
                raise ValidationError(_("The general sub-vertical cannot be deleted."))


class SubVerticalInline(admin.TabularInline):
    model = SubVertical
    formset = SubVerticalFormSet
    fields = ["name", "is_general", "risk", "allowed_terms", "recommended_term"]
    readonly_fields = ["is_general"]
    extra = 0


@admin.register(Vertical)
class VerticalAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "is_enabled", "updated_at"]
    list_filter = ["is_enabled"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [SubVerticalInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Every vertical has a general sub-vertical, also when created here
        vertical = form.instance
        if not vertical.sub_verticals.filter(is_general=True).exists():
            SubVertical.objects.create(vertical=vertical, **SubVertical.general_defaults())
