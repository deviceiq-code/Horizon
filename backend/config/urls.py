from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Sistema Horizon — Administração"
admin.site.site_title = "Sistema Horizon"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("contas.urls")),
]
