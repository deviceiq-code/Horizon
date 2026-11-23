from rest_framework import viewsets

from config.filters import NullsLastOrderingFilter
from config.keywords import KeywordSearchFilter
from config.parties import column_filters

from .models import Ownership, Warehouse
from .serializers import WarehouseSerializer


class WarehouseViewSet(viewsets.ModelViewSet):
    """CRUD for warehouses (Remarketing › Inventory).

    List supports ?search= (name, city, contact, verticals, provider's names, keywords),
    ?ownership=own|outsourced, ?vertical=<id> (warehouses serving it), ?service_provider=<id>,
    column filters (?name=, ?location=, ?is_active=), ?ordering=, ?page= and ?page_size=.
    """

    queryset = Warehouse.objects.select_related("service_provider").prefetch_related("verticals")
    serializer_class = WarehouseSerializer
    filter_backends = [KeywordSearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "name",
        "city",
        "contact_name",
        "verticals__name",
        "service_provider__name",
        "service_provider__trade_name",
    ]
    ordering_fields = ["id", "name", "ownership", "city", "state", "is_active"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        ownership = params.get("ownership", "")
        if ownership in Ownership.values:
            queryset = queryset.filter(ownership=ownership)
        vertical = params.get("vertical", "")
        if vertical.isdigit():
            queryset = queryset.filter(verticals__id=int(vertical)).distinct()
        provider = params.get("service_provider", "")
        if provider.isdigit():
            queryset = queryset.filter(service_provider_id=int(provider))
        return column_filters(queryset, params, names=("name",), tax_id=False)
