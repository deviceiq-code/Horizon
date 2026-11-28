from django.db.models import Count, ProtectedError, Q
from django.utils.translation import gettext as _
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.audit import AuditedViewSetMixin
from config.filters import NullsLastOrderingFilter
from config.keywords import KeywordSearchFilter
from config.parties import column_filters
from customers.models import ContractType
from customers.tax_ids import normalize_tax_id
from service_providers.models import ServiceKind

from . import hierarchy
from .models import BusinessEntity, EntityRole, SupplyKind
from .serializers import BusinessEntitySerializer, entity_ref


class TaxIdSearchFilter(KeywordSearchFilter):
    """Regular search (and keywords), plus the tax ID typed with or without punctuation
    ("11.222.333/0001-81"). `tax_id_field`: where the tax ID is (a role: "entity__tax_id")."""

    def filter_queryset(self, request, queryset, view):
        filtered = super().filter_queryset(request, queryset, view)
        tax_id = normalize_tax_id(request.query_params.get(self.search_param, ""))
        if len(tax_id) < 3:
            return filtered
        field = getattr(view, "tax_id_field", "tax_id")
        return queryset.filter(
            Q(pk__in=filtered.values("pk")) | Q(**{f"{field}__contains": tax_id})
        )


class BusinessEntityViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    """CRUD for business entities and their roles (docs/business-entities.md).

    List supports ?search= (names, tax ID, contact, e-mail, city, keywords, the customer's
    account managers), ?role=<role> (entities with it; then ?is_active= is the role's — and
    the entity's), ?contract_type=<type> (customers with it), ?account_manager=<user id>
    (customers it serves), ?service=<kind> (service providers offering it),
    ?supplies=products|services, ?parent=<id> (its branches), ?group=<id> (that entity and
    every branch under it), column filters (config.parties.column_filters: ?name=, ?tax_id=,
    ?location=, ?is_active=), ?ordering=, ?page= and ?page_size=. GET /counts/ gives how many
    there are in each tab; GET /parent-suggestion/?country=&tax_id=&exclude= the likely head
    office of a CNPJ.
    """

    queryset = BusinessEntity.objects.select_related(
        "parent",
        "customer__primary_account_manager",
        "supplier",
        "service_provider",
        "buyer",
    ).prefetch_related("customer__secondary_account_managers")
    serializer_class = BusinessEntitySerializer
    filter_backends = [TaxIdSearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "name",
        "trade_name",
        "contact_name",
        "email",
        "city",
        "customer__primary_account_manager__first_name",
        "customer__primary_account_manager__last_name",
        "customer__secondary_account_managers__first_name",
        "customer__secondary_account_managers__last_name",
    ]
    ordering_fields = [
        "id",
        "name",
        "trade_name",
        "tax_id",
        "city",
        "state",
        "is_active",
        "parent__name",
        "customer__primary_account_manager__first_name",
        "created_at",
    ]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset().annotate(branches_total=Count("branches"))
        if self.action != "list":
            return queryset
        params = self.request.query_params
        role = params.get("role", "")
        if role in EntityRole.values:
            queryset = queryset.filter(**{f"{role}__isnull": False})
        manager = params.get("account_manager", "")
        if manager.isdigit():
            queryset = queryset.filter(
                Q(customer__primary_account_manager_id=int(manager))
                | Q(customer__secondary_account_managers__id=int(manager))
            ).distinct()
        contract_type = params.get("contract_type", "")
        if contract_type in ContractType.values:
            queryset = queryset.filter(customer__contract_types__contains=[contract_type])
        service = params.get("service", "")
        if service in ServiceKind.values:
            queryset = queryset.filter(service_provider__services__contains=[service])
        supplies = params.get("supplies", "")
        if supplies in SupplyKind.values:
            queryset = queryset.filter(supplier__supplies__contains=[supplies])
        parent = params.get("parent", "")
        if parent.isdigit():
            queryset = queryset.filter(parent_id=int(parent))
        group = params.get("group", "")
        if group.isdigit():
            links = BusinessEntity.objects.values_list("id", "parent_id")
            queryset = queryset.filter(pk__in=hierarchy.descendants(int(group), links))
        # In a role's tab, "active" is the role's (and the entity's)
        active = params.get("is_active")
        if role in EntityRole.values and active in ("true", "false"):
            params = params.copy()
            params.pop("is_active")
            queryset = self._role_active(queryset, role, active == "true")
        return column_filters(queryset, params)

    @staticmethod
    def _role_active(queryset, role: str, active: bool):
        if active:
            return queryset.filter(is_active=True, **{f"{role}__is_active": True})
        return queryset.filter(Q(is_active=False) | Q(**{f"{role}__is_active": False}))

    def destroy(self, request, *args, **kwargs):
        entity = self.get_object()
        if entity.branches.exists():
            return Response(
                {"detail": _("This entity is the head office of others and cannot be deleted.")},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": _(
                        "Other records point to this entity (its roles' analyses, appointments, "
                        "warehouses, disposals…, or brands): it cannot be deleted. Deactivate it "
                        "instead."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=False, methods=["get"])
    def counts(self, request):
        """How many entities there are in each tab (all, then each role)."""
        totals = BusinessEntity.objects.aggregate(
            all=Count("id"),
            **{
                role: Count("id", filter=Q(**{f"{role}__isnull": False}))
                for role in EntityRole.values
            },
        )
        return Response(totals)

    @action(detail=False, methods=["get"], url_path="parent-suggestion")
    def parent_suggestion(self, request):
        """For a Brazilian CNPJ, the entity with the same root (the company) — its 0001 first:
        the likely head office. Only a suggestion; {"suggestion": null} when there is none."""
        params = request.query_params
        country = (params.get("country") or "BR").upper()
        tax_id = normalize_tax_id(params.get("tax_id", ""))
        root = hierarchy.cnpj_root(country, tax_id)
        if root is None or hierarchy.is_head_office_cnpj(tax_id):
            return Response({"suggestion": None})
        candidates = BusinessEntity.objects.filter(
            country=country, tax_id__startswith=root
        ).exclude(tax_id=tax_id)
        exclude = params.get("exclude", "")
        if exclude.isdigit():
            candidates = candidates.exclude(pk=int(exclude))
        ordered = sorted(
            candidates, key=lambda e: (not hierarchy.is_head_office_cnpj(e.tax_id), e.tax_id)
        )
        return Response({"suggestion": entity_ref(ordered[0]) if ordered else None})
