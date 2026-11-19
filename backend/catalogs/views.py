from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    DEFAULT_RECOMMENDED_TERM,
    DEFAULT_RISK,
    DEFAULT_TERMS,
    MAX_TERM_MONTHS,
    Vertical,
)
from .serializers import VerticalSerializer


class VerticalViewSet(viewsets.ModelViewSet):
    """CRUD for business verticals, with their sub-verticals nested.

    List supports ?search= (vertical, sub-vertical or account manager name), ?is_enabled=true
    or false, ?ordering= (id, name, is_enabled), ?page= and ?page_size=.

    Account managers are read-only here (`account_managers_detail`); they are assigned on the
    account manager (/api/account-managers/, field "verticals").

    Writes: "sub_verticals" is optional. When sent, it replaces the whole list (items with "id"
    are updated, items without it are created, missing ones are deleted) and must contain the
    general sub-vertical exactly once. When omitted on create, the general one gets defaults.
    """

    queryset = Vertical.objects.prefetch_related("account_managers", "sub_verticals")
    serializer_class = VerticalSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "sub_verticals__name", "account_managers__full_name"]
    ordering_fields = ["id", "name", "is_enabled"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("is_enabled", "").lower()
        if enabled in ("true", "false"):
            queryset = queryset.filter(is_enabled=enabled == "true")
        return queryset

    @action(detail=False, methods=["get"])
    def defaults(self, request):
        """Initial values for the general sub-vertical of a new vertical, and term limits."""
        return Response(
            {
                "risk": DEFAULT_RISK,
                "allowed_terms": DEFAULT_TERMS,
                "recommended_term": DEFAULT_RECOMMENDED_TERM,
                "max_term_months": MAX_TERM_MONTHS,
            }
        )
