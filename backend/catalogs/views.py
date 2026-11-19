import operator
from decimal import Decimal
from functools import reduce

from django.db.models import (
    CharField,
    DecimalField,
    ExpressionWrapper,
    F,
    Func,
    ProtectedError,
    Q,
    Value,
)
from django.utils.translation import gettext as _
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.filters import EnabledFilter, NullsLastOrderingFilter

from .models import (
    DEFAULT_RECOMMENDED_TERM,
    DEFAULT_RISK,
    DEFAULT_TERMS,
    MANUFACTURER_RATINGS,
    MAX_TERM_MONTHS,
    REMARKETING_RATINGS,
    AssetClass,
    Manufacturer,
    SubVertical,
    Vertical,
)
from .serializers import (
    AssetClassSerializer,
    ManufacturerSerializer,
    SubVerticalOptionSerializer,
    VerticalSerializer,
)


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
    filter_backends = [EnabledFilter, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "sub_verticals__name", "account_managers__full_name"]
    ordering_fields = ["id", "name", "is_enabled"]
    ordering = ["name"]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": _("This vertical has asset classes and cannot be deleted.")},
                status=status.HTTP_409_CONFLICT,
            )

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


def with_remarketing_score(queryset, fields):
    """Annotate `remarketing_score`: the average of the star ratings, for sorting in the database.

    It matches catalogs.ratings.average_stars (which the API returns as remarketing_average).
    """
    total = reduce(operator.add, (F(field) for field in fields))
    return queryset.annotate(
        remarketing_score=ExpressionWrapper(
            total / Value(Decimal(len(fields))),
            output_field=DecimalField(max_digits=4, decimal_places=2),
        )
    )


class ManufacturerViewSet(viewsets.ModelViewSet):
    """CRUD for manufacturers.

    List supports ?search= (name), ?is_enabled=true or false, ?ordering= (id, name, the three
    remarketing ratings, remarketing_score = their average, is_enabled), ?page= and ?page_size=.
    """

    queryset = with_remarketing_score(Manufacturer.objects.all(), MANUFACTURER_RATINGS)
    serializer_class = ManufacturerSerializer
    filter_backends = [EnabledFilter, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = [
        "id",
        "name",
        *MANUFACTURER_RATINGS,
        "remarketing_score",
        "is_enabled",
    ]
    ordering = ["name"]


class SubVerticalViewSet(viewsets.ReadOnlyModelViewSet):
    """Sub-verticals as options for pickers ("Industry / Yellow line"); edited in the vertical.

    List supports ?search= (vertical or sub-vertical name), ?is_enabled=true|false (of the
    vertical), ?page= and ?page_size=. Ordered by vertical, General first, then name.
    """

    queryset = SubVertical.objects.select_related("vertical").order_by(
        "vertical__name", "-is_general", "name"
    )
    serializer_class = SubVerticalOptionSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["vertical__name", "name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("is_enabled", "").lower()
        if enabled in ("true", "false"):
            queryset = queryset.filter(vertical__is_enabled=enabled == "true")
        return queryset


class AssetClassSearchFilter(filters.SearchFilter):
    """Regular search, plus any keyword containing the typed text."""

    def filter_queryset(self, request, queryset, view):
        filtered = super().filter_queryset(request, queryset, view)
        term = request.query_params.get(self.search_param, "").strip().lower()
        if not term:
            return filtered
        with_keywords = queryset.annotate(
            keywords_text=Func(
                F("keywords"), Value(" | "), function="array_to_string", output_field=CharField()
            )
        )
        return queryset.filter(
            Q(pk__in=filtered.values("pk"))
            | Q(pk__in=with_keywords.filter(keywords_text__contains=term).values("pk"))
        )


class AssetClassViewSet(viewsets.ModelViewSet):
    """CRUD for asset classes.

    List supports ?search= (name, keyword, sub-vertical or vertical name), ?vertical=<id>,
    ?sub_vertical=<id>, ?is_enabled=true|false, ?ordering= (id, name,
    sub_vertical__vertical__name, the four remarketing ratings, remarketing_score = their
    average, is_enabled), ?page= and ?page_size=.
    """

    queryset = with_remarketing_score(
        AssetClass.objects.select_related("sub_vertical__vertical"), REMARKETING_RATINGS
    )
    serializer_class = AssetClassSerializer
    filter_backends = [EnabledFilter, AssetClassSearchFilter, NullsLastOrderingFilter]
    search_fields = ["name", "sub_vertical__name", "sub_vertical__vertical__name"]
    ordering_fields = [
        "id",
        "name",
        "sub_vertical__vertical__name",
        *REMARKETING_RATINGS,
        "remarketing_score",
        "is_enabled",
    ]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("vertical", "").isdigit():
            queryset = queryset.filter(sub_vertical__vertical_id=int(params["vertical"]))
        if params.get("sub_vertical", "").isdigit():
            queryset = queryset.filter(sub_vertical_id=int(params["sub_vertical"]))
        return queryset
