from django.db.models import Q
from rest_framework import viewsets

from config.filters import NullsLastOrderingFilter
from config.parties import column_filters
from entities.views import TaxIdSearchFilter

from .models import ContractType, Customer
from .serializers import CustomerSerializer


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """Customers (the Customer role of business entities), read-only — for pickers and the
    search; they are written through /api/business-entities/.

    List supports ?contract_type=<type>, ?search= (name, trade name, tax ID, email, city,
    primary or secondary account manager), ?account_manager=<user id> (primary or
    secondary), column filters (config.parties.column_filters: ?name=, ?tax_id=, ?location=,
    ?is_active= — active in the role and as an entity), ?ordering=, ?page= and ?page_size=.
    """

    queryset = Customer.objects.select_related(
        "entity", "primary_account_manager"
    ).prefetch_related("secondary_account_managers")
    serializer_class = CustomerSerializer
    filter_backends = [TaxIdSearchFilter, NullsLastOrderingFilter]
    keywords_lookup = "entity__keywords"
    tax_id_field = "entity__tax_id"
    search_fields = [
        "entity__name",
        "entity__trade_name",
        "entity__email",
        "entity__city",
        "primary_account_manager__first_name",
        "primary_account_manager__last_name",
        "secondary_account_managers__first_name",
        "secondary_account_managers__last_name",
    ]
    ordering_fields = [
        "id",
        "entity__name",
        "entity__trade_name",
        "entity__tax_id",
        "entity__city",
        "is_active",
        "primary_account_manager__first_name",
    ]
    ordering = ["entity__name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        contract_type = params.get("contract_type", "")
        if contract_type in ContractType.values:
            queryset = queryset.filter(contract_types__contains=[contract_type])
        manager = params.get("account_manager", "")
        if manager.isdigit():
            queryset = queryset.filter(
                Q(primary_account_manager_id=int(manager))
                | Q(secondary_account_managers__id=int(manager))
            ).distinct()
        return column_filters(queryset, params, prefix="entity__")
