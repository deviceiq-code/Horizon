from django.db.models import Count, Q
from django.utils.translation import gettext_noop
from rest_framework import viewsets

from catalogs.views import RefuseDeletingWhenInUse
from config.filters import NullsLastOrderingFilter
from config.keywords import KeywordSearchFilter
from config.parties import column_filters
from customers.tax_ids import normalize_tax_id

from .models import ServiceKind, ServiceProvider
from .serializers import ServiceProviderSerializer


class ServiceProviderSearchFilter(KeywordSearchFilter):
    """Regular search (and keywords), plus the tax ID typed with or without punctuation."""

    def filter_queryset(self, request, queryset, view):
        filtered = super().filter_queryset(request, queryset, view)
        tax_id = normalize_tax_id(request.query_params.get(self.search_param, ""))
        if len(tax_id) < 3:
            return filtered
        return queryset.filter(Q(pk__in=filtered.values("pk")) | Q(tax_id__contains=tax_id))


class ServiceProviderViewSet(RefuseDeletingWhenInUse, viewsets.ModelViewSet):
    """CRUD for service providers.

    List supports ?search= (legal/trade name, tax ID, contact, email, city, keywords),
    ?service=<kind> (providers offering it), column filters (config.parties.column_filters:
    ?name=, ?tax_id=, ?location=, ?is_active=), ?ordering=, ?page= and
    ?page_size=. Deleting one that runs warehouses answers 409.
    """

    queryset = ServiceProvider.objects.annotate(warehouses_total=Count("warehouses"))
    serializer_class = ServiceProviderSerializer
    filter_backends = [ServiceProviderSearchFilter, NullsLastOrderingFilter]
    search_fields = ["name", "trade_name", "contact_name", "email", "city"]
    ordering_fields = ["id", "name", "trade_name", "tax_id", "city", "state", "is_active"]
    ordering = ["name"]
    in_use_message = gettext_noop("This service provider runs warehouses and cannot be deleted.")

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        service = params.get("service", "")
        if service in ServiceKind.values:
            queryset = queryset.filter(services__contains=[service])
        return column_filters(queryset, params)
