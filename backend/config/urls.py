from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

admin.site.site_header = _("Horizon System — Administration")
admin.site.site_title = _("Horizon System")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/account-managers/", include("account_managers.urls")),
    path("api/customers/", include("customers.urls")),
    path("api/catalogs/", include("catalogs.urls")),
    path("api/average-prices/", include("pricing.urls")),
    path("api/system/", include("system.urls")),
    path("api/", include("users.urls")),
]
