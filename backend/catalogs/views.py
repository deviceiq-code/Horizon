import operator
from decimal import Decimal, InvalidOperation
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
from django.utils.translation import gettext_noop
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.filters import EnabledFilter, NullsLastOrderingFilter
from config.keywords import KeywordSearchFilter

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
    SpecTemplateSerializer,
    SubVerticalOptionSerializer,
    VerticalSerializer,
)


class VerticalViewSet(viewsets.ModelViewSet):
    """CRUD for business verticals, with their sub-verticals nested.

    List supports ?search= (vertical, sub-vertical or account manager name), ?is_enabled=true
    or false, column filters ?name= (name or keyword) and ?account_manager=<user id>,
    ?ordering= (id, name, is_enabled), ?page= and ?page_size=.

    Account managers are read-only here (`account_managers_detail`); they are assigned on the
    account manager (/api/account-managers/, field "verticals").

    Writes: "sub_verticals" is optional. When sent, it replaces the whole list (items with "id"
    are updated, items without it are created, missing ones are deleted) and must contain the
    general sub-vertical exactly once. When omitted on create, the general one gets defaults.
    """

    queryset = Vertical.objects.prefetch_related(
        "account_manager_profiles__user__roles", "sub_verticals"
    )
    serializer_class = VerticalSerializer
    filter_backends = [EnabledFilter, KeywordSearchFilter, filters.OrderingFilter]
    search_fields = [
        "name",
        "sub_verticals__name",
        "account_manager_profiles__user__first_name",
        "account_manager_profiles__user__last_name",
    ]
    ordering_fields = ["id", "name", "is_enabled"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        name = " ".join(params.get("name", "").split()).lower()
        if name:
            queryset = queryset.annotate(
                keywords_text=Func(
                    F("keywords"),
                    Value(" | "),
                    function="array_to_string",
                    output_field=CharField(),
                )
            ).filter(Q(name__icontains=name) | Q(keywords_text__contains=name))
        manager = params.get("account_manager", "")
        if manager.isdigit():
            queryset = queryset.filter(account_manager_profiles__user_id=int(manager)).distinct()
        return queryset

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": _(
                        "This vertical is in use (asset classes, eFMV analyses or warehouses) "
                        "and cannot be deleted."
                    )
                },
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


class RefuseDeletingWhenInUse:
    """DELETE answers 409 with `in_use_message` when other records protect the row."""

    in_use_message = ""

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({"detail": _(self.in_use_message)}, status=status.HTTP_409_CONFLICT)


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


def name_and_rating_filters(queryset, params):
    """Column filters of the catalog grids with remarketing ratings: ?name= (name or keyword)
    and ?remarketing_min= (remarketing average at least, 0–5; needs `remarketing_score`)."""
    name = " ".join(params.get("name", "").split()).lower()
    if name:
        with_keywords = queryset.annotate(
            keywords_text=Func(
                F("keywords"),
                Value(" | "),
                function="array_to_string",
                output_field=CharField(),
            )
        )
        queryset = with_keywords.filter(Q(name__icontains=name) | Q(keywords_text__contains=name))
    try:
        minimum = Decimal(params.get("remarketing_min", ""))
    except (InvalidOperation, ValueError):
        minimum = None
    if minimum is not None and minimum.is_finite():
        queryset = queryset.filter(remarketing_score__gte=minimum)
    return queryset


class ManufacturerViewSet(RefuseDeletingWhenInUse, viewsets.ModelViewSet):
    """CRUD for manufacturers.

    List supports ?search= (name), ?is_enabled=true or false, column filters ?name= (name or
    keyword) and ?remarketing_min=, ?ordering= (id, name, the three remarketing ratings,
    remarketing_score = their average, is_enabled), ?page= and ?page_size=.
    """

    queryset = with_remarketing_score(Manufacturer.objects.all(), MANUFACTURER_RATINGS)
    in_use_message = gettext_noop(
        "This manufacturer is used in average prices and cannot be deleted."
    )
    serializer_class = ManufacturerSerializer
    filter_backends = [EnabledFilter, KeywordSearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = [
        "id",
        "name",
        *MANUFACTURER_RATINGS,
        "remarketing_score",
        "is_enabled",
    ]
    ordering = ["name"]

    def get_queryset(self):
        return name_and_rating_filters(super().get_queryset(), self.request.query_params)


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


class AssetClassViewSet(RefuseDeletingWhenInUse, viewsets.ModelViewSet):
    """CRUD for asset classes.

    List supports ?search= (name, keyword, sub-vertical or vertical name), ?vertical=<id>,
    ?sub_vertical=<id>, ?is_enabled=true|false, ?name= (name or keyword contains),
    ?remarketing_min= (remarketing average at least, 0–5), ?ordering= (id, name,
    sub_vertical__vertical__name, the four remarketing ratings, remarketing_score = their
    average, is_enabled), ?page= and ?page_size=.
    """

    queryset = with_remarketing_score(
        AssetClass.objects.select_related("sub_vertical__vertical"), REMARKETING_RATINGS
    )
    in_use_message = gettext_noop(
        "This asset class is used in average prices and cannot be deleted."
    )
    serializer_class = AssetClassSerializer
    filter_backends = [EnabledFilter, KeywordSearchFilter, NullsLastOrderingFilter]
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

    @action(detail=True, methods=["get", "put"], url_path="spec-template")
    def spec_template(self, request, pk=None):
        """GET the asset class's specification template; PUT {"fields": [...]} replaces it."""
        asset_class = self.get_object()
        if request.method == "PUT":
            serializer = SpecTemplateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            asset_class.spec_template = serializer.validated_data["fields"]
            asset_class.save(update_fields=["spec_template", "updated_at"])
        return Response({"fields": asset_class.spec_template})

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("vertical", "").isdigit():
            queryset = queryset.filter(sub_vertical__vertical_id=int(params["vertical"]))
        if params.get("sub_vertical", "").isdigit():
            queryset = queryset.filter(sub_vertical_id=int(params["sub_vertical"]))
        return name_and_rating_filters(queryset, params)
