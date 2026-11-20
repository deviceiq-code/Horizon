import re

from django.db.models import Prefetch
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import EfmvAnalysis, EfmvScenario
from .serializers import (
    EfmvAnalysisListSerializer,
    EfmvAnalysisSerializer,
    ScenarioPreviewSerializer,
)

CODE = re.compile(r"^\s*EFMV-(\d{4})-(\d+)\s*$", re.IGNORECASE)


class AnalysisSearchFilter(filters.SearchFilter):
    """Regular search, and a code ("EFMV-2026-0001") finds that analysis."""

    def filter_queryset(self, request, queryset, view):
        term = request.query_params.get(self.search_param, "")
        match = CODE.match(term)
        if match:
            return queryset.filter(year=int(match[1]), sequence=int(match[2]))
        return super().filter_queryset(request, queryset, view)


class AnalysisOrderingFilter(filters.OrderingFilter):
    """`code` sorts by year and sequence."""

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        result = []
        for field in ordering or []:
            if field.lstrip("-") == "code":
                sign = "-" if field.startswith("-") else ""
                result += [f"{sign}year", f"{sign}sequence"]
            else:
                result.append(field)
        return result


class EfmvAnalysisViewSet(viewsets.ModelViewSet):
    """eFMV analyses. ?search= (code, customer, account manager), ?account_manager=<user id>,
    ?customer=<id>, ?ordering= (created_at, code, customer__name). Sending `scenarios` replaces
    them. POST /scenario-preview/ {term_months, items: [{average_price, quantity}]} returns the
    totals of a scenario being edited."""

    queryset = EfmvAnalysis.objects.select_related(
        "account_manager", "customer", "created_by"
    ).prefetch_related(
        Prefetch(
            "scenarios",
            queryset=EfmvScenario.objects.select_related(
                "vertical", "sub_vertical__vertical"
            ).prefetch_related("items"),
        )
    )
    filter_backends = [AnalysisSearchFilter, AnalysisOrderingFilter]
    search_fields = [
        "customer__name",
        "customer__trade_name",
        "account_manager__first_name",
        "account_manager__last_name",
        "scenarios__name",
    ]
    ordering_fields = ["code", "created_at", "customer__name", "account_manager__first_name"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        if self.action == "list":
            return EfmvAnalysisListSerializer
        return EfmvAnalysisSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for param, field in (
            ("account_manager", "account_manager_id"),
            ("customer", "customer_id"),
        ):
            if params.get(param, "").isdigit():
                queryset = queryset.filter(**{field: int(params[param])})
        return queryset.distinct()

    @action(detail=False, methods=["post"], url_path="scenario-preview")
    def scenario_preview(self, request):
        serializer = ScenarioPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.to_representation(serializer.validated_data))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        analysis = serializer.save()
        data = EfmvAnalysisSerializer(
            self.get_queryset().get(pk=analysis.pk), context=self.get_serializer_context()
        ).data
        return Response(data, status=status.HTTP_201_CREATED)
