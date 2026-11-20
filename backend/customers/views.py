from django.db.models import Q
from rest_framework import filters, viewsets

from config.filters import NullsLastOrderingFilter

from .models import Customer
from .serializers import CustomerSerializer
from .tax_ids import normalize_tax_id


class CustomerSearchFilter(filters.SearchFilter):
    """Regular search, plus tax ID typed with or without punctuation ("11.222.333/0001-81")."""

    def filter_queryset(self, request, queryset, view):
        filtered = super().filter_queryset(request, queryset, view)
        term = request.query_params.get(self.search_param, "")
        tax_id = normalize_tax_id(term)
        if len(tax_id) < 3:
            return filtered
        return queryset.filter(Q(pk__in=filtered.values("pk")) | Q(tax_id__contains=tax_id))


class CustomerViewSet(viewsets.ModelViewSet):
    """CRUD for customers.

    List supports ?search= (name, trade name, tax ID, email, city, primary or secondary
    account manager), ?account_manager=<user id> (primary or secondary), ?is_active=true|false,
    ?ordering=, ?page= and ?page_size=.
    """

    queryset = Customer.objects.select_related("primary_account_manager").prefetch_related(
        "secondary_account_managers"
    )
    serializer_class = CustomerSerializer
    filter_backends = [CustomerSearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "name",
        "trade_name",
        "email",
        "city",
        "primary_account_manager__first_name",
        "primary_account_manager__last_name",
        "secondary_account_managers__first_name",
        "secondary_account_managers__last_name",
    ]
    ordering_fields = [
        "id",
        "name",
        "trade_name",
        "tax_id",
        "city",
        "state",
        "is_active",
        "primary_account_manager__first_name",
    ]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        manager = params.get("account_manager", "")
        if manager.isdigit():
            queryset = queryset.filter(
                Q(primary_account_manager_id=int(manager))
                | Q(secondary_account_managers__id=int(manager))
            ).distinct()
        active = params.get("is_active")
        if active in ("true", "false"):
            queryset = queryset.filter(is_active=active == "true")
        return queryset
