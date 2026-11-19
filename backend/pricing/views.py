from django.db.models import Prefetch
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AveragePrice, PricePoint
from .serializers import (
    AveragePriceCreateSerializer,
    AveragePriceDetailSerializer,
    AveragePricePreviewSerializer,
    AveragePriceSerializer,
)

FILTERS = {
    "vertical": "sub_vertical__vertical_id",
    "sub_vertical": "sub_vertical_id",
    "asset_class": "asset_class_id",
    "manufacturer": "manufacturer_id",
}


class AveragePriceViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Average prices. Rows are never edited (no PUT/PATCH): to change one, POST a new row with
    "supersedes": <id>; the old one is kept as a previous version. DELETE only hides a row.

    List (current versions, not deleted) supports ?search= (model, description, asset class,
    manufacturer, vertical or sub-vertical), ?vertical=, ?sub_vertical=, ?asset_class=,
    ?manufacturer= (ids), ?ordering= (created_at, model, original_value, asset_class__name,
    manufacturer__name), ?page= and ?page_size=. GET /<id>/ includes the monthly curve and works
    for previous versions too; GET /<id>/history/ lists every version of the row.
    POST /preview/ resolves values typed in the form (nothing saved).
    """

    queryset = AveragePrice.objects.select_related(
        "sub_vertical__vertical", "asset_class", "manufacturer", "created_by"
    ).prefetch_related(
        Prefetch("points", queryset=PricePoint.objects.select_related("average_price"))
    )
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "model",
        "description",
        "asset_class__name",
        "manufacturer__name",
        "sub_vertical__name",
        "sub_vertical__vertical__name",
    ]
    ordering_fields = [
        "created_at",
        "model",
        "original_value",
        "asset_class__name",
        "manufacturer__name",
    ]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            queryset = queryset.active()
            for param, field in FILTERS.items():
                value = self.request.query_params.get(param, "")
                if value.isdigit():
                    queryset = queryset.filter(**{field: int(value)})
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return AveragePriceCreateSerializer
        if self.action == "retrieve":
            return AveragePriceDetailSerializer
        return AveragePriceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = serializer.save()
        row = self.get_queryset().get(pk=row.pk)
        return Response(AveragePriceDetailSerializer(row).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Hide the row (kept for history). Only current, not deleted rows."""
        row = self.get_object()
        if not row.is_current or row.deleted_at is not None:
            return Response(
                {"detail": _("Only the current version of an average price can be deleted.")},
                status=status.HTTP_409_CONFLICT,
            )
        row.deleted_at = timezone.now()
        row.deleted_by = request.user
        row.save(update_fields=["deleted_at", "deleted_by"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def preview(self, request):
        """Resolved values, warnings and monthly curve for the values being typed (not saved)."""
        serializer = AveragePricePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.to_representation(serializer.validated_data))

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Every version of the row, newest first."""
        versions = self.get_object().versions()
        ids = [v.pk for v in versions]
        rows = {r.pk: r for r in self.get_queryset().filter(pk__in=ids)}
        return Response(AveragePriceSerializer([rows[i] for i in ids], many=True).data)
