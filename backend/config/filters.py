from django.db.models import F
from rest_framework.filters import BaseFilterBackend, OrderingFilter


class EnabledFilter(BaseFilterBackend):
    """?is_enabled=true|false keeps only enabled or disabled records (any other value: all)."""

    def filter_queryset(self, request, queryset, view):
        value = request.query_params.get("is_enabled", "").lower()
        if value in ("true", "false"):
            return queryset.filter(is_enabled=value == "true")
        return queryset


class NullsLastOrderingFilter(OrderingFilter):
    """Like OrderingFilter, but empty (NULL) values always go last, in both directions.

    PostgreSQL puts NULLs first on descending order, which in a grid looks like blank rows
    at the top when sorting Z→A by an optional column (e.g. a customer's account manager).
    """

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        return queryset.order_by(
            *(
                F(field[1:]).desc(nulls_last=True)
                if field.startswith("-")
                else F(field).asc(nulls_last=True)
                for field in ordering
            )
        )
