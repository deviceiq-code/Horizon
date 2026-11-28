import re

from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from config.keywords import KeywordSearchFilter
from customers.models import Customer
from users.display import full_name_in
from users.models import UserProfile, is_account_manager, user_photo_version

from .models import EfmvAnalysis, EfmvScenario
from .serializers import (
    EfmvAnalysisListSerializer,
    EfmvAnalysisSerializer,
    ScenarioPreviewSerializer,
)

CODE = re.compile(r"^\s*EFMV-(\d{4})-(\d+)\s*$", re.IGNORECASE)


class AnalysisSearchFilter(KeywordSearchFilter):
    """Regular search (and keywords), and a code ("EFMV-2026-0001") finds that analysis."""

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
    ?customer=<id>, ?ordering= (created_at, code, customer__entity__name). Sending `scenarios`
    replaces them. POST /scenario-preview/ {term_months, items: [{average_price, quantity}]}
    returns the totals of a scenario being edited."""

    queryset = EfmvAnalysis.objects.select_related(
        "account_manager",
        "customer__entity",
        "created_by",
        "updated_by",
        "vertical",
        "sub_vertical__vertical",
    ).prefetch_related(
        Prefetch("scenarios", queryset=EfmvScenario.objects.prefetch_related("items"))
    )
    filter_backends = [AnalysisSearchFilter, AnalysisOrderingFilter]
    search_fields = [
        "external_reference",
        "customer__entity__name",
        "customer__entity__trade_name",
        "account_manager__first_name",
        "account_manager__last_name",
        "scenarios__name",
    ]
    ordering_fields = [
        "code",
        "created_at",
        "updated_at",
        "customer__entity__name",
        "account_manager__first_name",
    ]
    # The latest updated first
    ordering = ["-updated_at", "-id"]

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

    @action(detail=False, methods=["get"], url_path="account-manager-summary")
    def account_manager_summary(self, request):
        """What the wizard shows about an account manager (?account_manager=<user id>): who
        they are, how many analyses they have, their 5 verticals with most analyses and how
        many active customers they are the primary account manager of."""
        raw = request.query_params.get("account_manager", "")
        if not raw.isdigit():
            raise ValidationError({"account_manager": ["A user id is required."]})
        user = get_object_or_404(get_user_model(), pk=int(raw), is_active=True)
        if not is_account_manager(user):
            raise ValidationError({"account_manager": ["This user is not an account manager."]})
        profile = UserProfile.for_user(user)
        analyses = EfmvAnalysis.objects.filter(account_manager=user)
        top = (
            analyses.exclude(vertical=None)
            .values("vertical_id", "vertical__name")
            .annotate(analyses=Count("id"))
            .order_by("-analyses", "vertical__name")[:5]
        )
        return Response(
            {
                "id": user.pk,
                "full_name": full_name_in(self.get_serializer_context(), user),
                "email": user.email,
                "job_title": profile.job_title,
                "photo_version": user_photo_version(user),
                # The verticals they work in: the ones a new analysis of theirs can be in
                "verticals": [
                    {"id": v.pk, "name": v.name} for v in profile.verticals.order_by("name")
                ],
                "analyses_count": analyses.count(),
                "top_verticals": [
                    {"id": v["vertical_id"], "name": v["vertical__name"], "analyses": v["analyses"]}
                    for v in top
                ],
                "primary_customers_count": Customer.objects.filter(
                    primary_account_manager=user, is_active=True
                ).count(),
            }
        )

    @action(detail=False, methods=["post"], url_path="scenario-preview")
    def scenario_preview(self, request):
        serializer = ScenarioPreviewSerializer(data=request.data, context={"request": request})
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
