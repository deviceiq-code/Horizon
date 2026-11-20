from django.contrib import admin

from .models import EfmvAnalysis, EfmvScenario, EfmvScenarioItem


class ScenarioInline(admin.TabularInline):
    model = EfmvScenario
    extra = 0


@admin.register(EfmvAnalysis)
class EfmvAnalysisAdmin(admin.ModelAdmin):
    list_display = ["code", "customer", "account_manager", "created_at"]
    inlines = [ScenarioInline]


admin.site.register(EfmvScenarioItem)
