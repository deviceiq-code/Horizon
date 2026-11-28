from django.db.models import Count
from rest_framework import viewsets

from config.filters import NullsLastOrderingFilter
from config.parties import column_filters
from entities.views import TaxIdSearchFilter

from .models import ServiceKind, ServiceProvider
from .serializers import ServiceProviderSerializer


class ServiceProviderViewSet(viewsets.ReadOnlyModelViewSet):
    """Service providers (the Service Provider role of business entities), read-only — for
    pickers; they are written through /api/business-entities/.

    List supports ?search= (legal/trade name, tax ID, contact, email, city, keywords),
    ?service=<kind> (providers offering it), column filters (config.parties.column_filters:
    ?name=, ?tax_id=, ?location=, ?is_active= — active in the role and as an entity),
    ?ordering=, ?page= and ?page_size=.
    """

    queryset = ServiceProvider.objects.select_related("entity").annotate(
        warehouses_total=Count("warehouses")
    )
    serializer_class = ServiceProviderSerializer
    filter_backends = [TaxIdSearchFilter, NullsLastOrderingFilter]
    keywords_lookup = "entity__keywords"
    tax_id_field = "entity__tax_id"
    search_fields = [
        "entity__name",
        "entity__trade_name",
        "entity__contact_name",
        "entity__email",
        "entity__city",
    ]
    ordering_fields = ["id", "entity__name", "entity__trade_name", "entity__city", "is_active"]
    ordering = ["entity__name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        service = params.get("service", "")
        if service in ServiceKind.values:
            queryset = queryset.filter(services__contains=[service])
        return column_filters(queryset, params, prefix="entity__")
