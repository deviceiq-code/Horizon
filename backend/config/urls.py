from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

admin.site.site_header = _("Horizon — Administration")
admin.site.site_title = _("Horizon")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/customers/", include("customers.urls")),
    path("api/service-providers/", include("service_providers.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/catalogs/", include("catalogs.urls")),
    path("api/average-prices/", include("pricing.urls")),
    path("api/efmv-analyses/", include("efmv.urls")),
    path("api/pricing/", include("pricing.control_panel")),
    # One search over every module (search/registry.py)
    path("api/search/", include("search.urls")),
    path("api/", include("users.urls")),
]
