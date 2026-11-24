import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Exists, F, Min, OuterRef, Prefetch, Q
from django.http import FileResponse, Http404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogs.models import AssetClass, AssetModel, PhotoKind
from catalogs.views import RefuseDeletingWhenInUse
from config.filters import NullsLastOrderingFilter
from config.keywords import KeywordSearchFilter
from config.parties import column_filters
from pricing.documents import content_type_for, opens_inline
from users.models import INVENTORY_SUPERVISOR
from users.permissions import is_administrator

from . import disposals, followups, inspection, receiving, services, transfers
from .expected import model_key, parse_pasted
from .models import (
    BEFORE_SENDING,
    OPEN_DISPOSAL,
    AccessoryBalance,
    AccessoryCondition,
    AgingLimit,
    Alert,
    Appointment,
    AppointmentKind,
    AppointmentStatus,
    Asset,
    AttachmentKind,
    BlockFollowUp,
    BlockStatus,
    Container,
    ContainerKind,
    DeadlineSetting,
    Disposal,
    DisposalItem,
    DisposalKind,
    DisposalStatus,
    Dispute,
    DisputeStatus,
    ErasureTool,
    ExpectedItem,
    Finding,
    FindingKind,
    FindingStatus,
    GradeLevel,
    Holiday,
    InspectionReport,
    LabelRange,
    Location,
    LotErasureTool,
    LotStatus,
    MovementEvent,
    Occurrence,
    OccurrenceKind,
    OccurrenceStatus,
    Ownership,
    PenaltyRate,
    ReceivingLot,
    ReportStatus,
    Transfer,
    TransferStatus,
    Warehouse,
)
from .permissions import (
    DISPOSERS,
    EXPECTED_READERS,
    INSPECTORS,
    LABELERS,
    LOCATION_KEEPERS,
    MOVERS,
    PICKERS,
    RECEIVERS,
    SCHEDULERS,
    SENDERS,
    SUPERVISORS,
    TRANSFER_HANDLERS,
    TRANSFER_REQUESTERS,
    has_role,
    role_permission,
)
from .serializers import (
    AccessoryBalanceSerializer,
    AgingLimitSerializer,
    AlertSerializer,
    AppointmentSerializer,
    AssetSerializer,
    BlockFollowUpSerializer,
    ChargeFindingSerializer,
    ContainerSerializer,
    DeadlineSettingSerializer,
    DisposalFileSerializer,
    DisposalItemSerializer,
    DisposalSerializer,
    DisputeSerializer,
    ErasureToolSerializer,
    EvidenceSerializer,
    ExpectedItemSerializer,
    FindingSerializer,
    GradeLevelSerializer,
    HolidaySerializer,
    InspectionReportListSerializer,
    InspectionReportSerializer,
    LabelRangeSerializer,
    LocationSerializer,
    LotAttachmentSerializer,
    LotErasureToolSerializer,
    LotOpenSerializer,
    MovementEventSerializer,
    MovementSerializer,
    OccurrenceSerializer,
    PenaltyRateSerializer,
    ReceivingLotSerializer,
    ReportPhotoSerializer,
    StockAssetSerializer,
    TransferFileSerializer,
    TransferItemSerializer,
    TransferSerializer,
    WarehouseSerializer,
    asset_class_name,
)
from .states import AreaType, AssetStatus, DomainError


class WarehouseViewSet(viewsets.ModelViewSet):
    """CRUD for warehouses (Remarketing › Inventory).

    List supports ?search= (name, city, contact, verticals, provider's names, keywords),
    ?ownership=own|outsourced, ?vertical=<id> (warehouses serving it), ?service_provider=<id>,
    column filters (?name=, ?location=, ?is_active=), ?ordering=, ?page= and ?page_size=.
    """

    queryset = Warehouse.objects.select_related("service_provider").prefetch_related("verticals")
    serializer_class = WarehouseSerializer
    filter_backends = [KeywordSearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "name",
        "code",
        "city",
        "contact_name",
        "verticals__name",
        "service_provider__name",
        "service_provider__trade_name",
    ]
    ordering_fields = ["id", "name", "code", "ownership", "city", "state", "is_active"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        ownership = params.get("ownership", "")
        if ownership in Ownership.values:
            queryset = queryset.filter(ownership=ownership)
        vertical = params.get("vertical", "")
        if vertical.isdigit():
            queryset = queryset.filter(verticals__id=int(vertical)).distinct()
        provider = params.get("service_provider", "")
        if provider.isdigit():
            queryset = queryset.filter(service_provider_id=int(provider))
        return column_filters(queryset, params, names=("name",), tax_id=False)


# --- Foundation: locations, containers, assets, movements, labels ----------------------------


def domain_error(exc: DomainError) -> Response:
    """A business rule refused it: 400 with the translated reason (and the field, if any)."""
    return Response(
        {"detail": str(exc.message), "field": exc.field}, status=status.HTTP_400_BAD_REQUEST
    )


class LocationViewSet(RefuseDeletingWhenInUse, viewsets.ModelViewSet):
    """Locations of the warehouses (a tree), plus the virtual transit location.

    List supports ?warehouse=<id>, ?parent=<id> or ?parent=none (top level), ?area_type=,
    ?is_active=, ?search= (code, description), ?ordering= (code, area_type), pagination.
    GET tree/?warehouse=<id> returns the whole tree of a warehouse (nested `children`).
    Writing: administrators and inventory supervisors. Deleting a location that has
    sub-locations, assets, containers or history answers 409 (deactivate it instead).
    """

    queryset = Location.objects.select_related("warehouse").annotate(
        children_count=Count("children", distinct=True),
        assets_count=Count("assets", distinct=True),
        containers_count=Count("containers", distinct=True),
    )
    serializer_class = LocationSerializer
    permission_classes = [role_permission(*LOCATION_KEEPERS)]
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = ["code", "description"]
    ordering_fields = ["code", "area_type", "is_active"]
    ordering = ["code"]
    in_use_message = gettext_noop(
        "This location has sub-locations, assets, containers or history and cannot be deleted. "
        "Deactivate it instead."
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("warehouse", "").isdigit():
            queryset = queryset.filter(warehouse_id=int(params["warehouse"]))
        parent = params.get("parent", "")
        if parent == "none":
            queryset = queryset.filter(parent__isnull=True)
        elif parent.isdigit():
            queryset = queryset.filter(parent_id=int(parent))
        if params.get("area_type") in AreaType.values:
            queryset = queryset.filter(area_type=params["area_type"])
        if params.get("is_active") in ("true", "false"):
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        return queryset

    def destroy(self, request, *args, **kwargs):
        location = self.get_object()
        if location.is_virtual:
            return Response(
                {"detail": _("The virtual location cannot be deleted.")},
                status=status.HTTP_409_CONFLICT,
            )
        if MovementEvent.objects.filter(
            Q(from_location=location) | Q(to_location=location)
        ).exists():
            return Response({"detail": _(self.in_use_message)}, status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def tree(self, request):
        warehouse = request.query_params.get("warehouse", "")
        if not warehouse.isdigit():
            return Response({"warehouse": [_("This field is required.")]}, status=400)
        rows = self.get_serializer(
            self.get_queryset().filter(warehouse_id=int(warehouse)).order_by("code"), many=True
        ).data
        by_parent: dict = {}
        for row in rows:
            by_parent.setdefault(row["parent"], []).append({**row, "children": []})
        for children in by_parent.values():
            for node in children:
                node["children"] = by_parent.get(node["id"], [])
        return Response(by_parent.get(None, []))


class ContainerViewSet(viewsets.ModelViewSet):
    """Boxes, cages and pallets. Created at a location (POST {kind, current_location}); moved
    only through movements. ?search= (code, description), ?kind=, ?location=<id>,
    ?warehouse=<id>, ?is_active=. Deleting one with history answers 409 (deactivate it)."""

    queryset = Container.objects.select_related("current_location").annotate(
        assets_count=Count("assets")
    )
    serializer_class = ContainerSerializer
    permission_classes = [role_permission(*LABELERS)]
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = ["code", "description", "current_location__code"]
    ordering_fields = ["code", "kind", "current_location__code", "is_active"]
    ordering = ["-code"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("kind") in ContainerKind.values:
            queryset = queryset.filter(kind=params["kind"])
        if params.get("location", "").isdigit():
            queryset = queryset.filter(current_location_id=int(params["location"]))
        if params.get("warehouse", "").isdigit():
            queryset = queryset.filter(current_location__warehouse_id=int(params["warehouse"]))
        if params.get("is_active") in ("true", "false"):
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            container = services.create_container(
                kind=serializer.validated_data["kind"],
                location=serializer.validated_data["current_location"],
                description=serializer.validated_data.get("description", ""),
                user=request.user,
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response(self.get_serializer(container).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": _("Containers keep their history: deactivate it instead.")},
            status=status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"])
    def reprint(self, request, pk=None):
        container = self.get_object()
        services.reprint_label(container, user=request.user, reason=request.data.get("reason", ""))
        return Response(self.get_serializer(container).data)


class AssetViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Assets in stock. Never deleted (their history stays).

    List supports ?search= (Horizon ID, serial, model, manufacturer), ?status=, ?warehouse=,
    ?location=, ?container=, ?asset_model=, ?asset_class=, ?name= (Horizon ID, serial or model
    contains), ?ordering=, pagination. GET <id>/ includes `events` (its whole history).
    Assets enter through the triage of receiving lots (/lots/<id>/units/).
    PATCH: notes and other IDs only. POST <id>/reprint/: label printed again (RN-16).
    """

    queryset = Asset.objects.select_related(
        "asset_model__manufacturer",
        "asset_model__asset_class",
        "current_location__warehouse",
        "current_container",
    )
    serializer_class = AssetSerializer
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "horizon_id",
        "serial",
        "asset_model__name",
        "asset_model__manufacturer__name",
    ]
    ordering_fields = [
        "horizon_id",
        "serial",
        "status",
        "asset_model__name",
        "current_location__code",
        "created_at",
        "updated_at",
    ]
    ordering = ["-horizon_id"]

    def get_permissions(self):
        if self.action in ("new_report", "disassemble"):
            return [role_permission(*INSPECTORS)()]
        if self.action == "reprint":
            return [role_permission(*LABELERS)()]
        return [role_permission(*MOVERS)()]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("status") in AssetStatus.values:
            queryset = queryset.filter(status=params["status"])
        for param, lookup in (
            ("warehouse", "current_location__warehouse_id"),
            ("location", "current_location_id"),
            ("container", "current_container_id"),
            ("asset_model", "asset_model_id"),
            ("asset_class", "asset_model__asset_class_id"),
        ):
            if params.get(param, "").isdigit():
                queryset = queryset.filter(**{lookup: int(params[param])})
        name = " ".join(params.get("name", "").split())
        if name:
            queryset = queryset.filter(
                Q(horizon_id__icontains=name)
                | Q(serial__icontains=name)
                | Q(asset_model__name__icontains=name)
                | Q(asset_model__manufacturer__name__icontains=name)
            )
        return queryset

    def retrieve(self, request, *args, **kwargs):
        asset = self.get_object()
        data = self.get_serializer(asset).data
        events = asset.events.select_related(
            "user", "from_location", "to_location", "from_container", "to_container", "container"
        ).order_by("-at", "-id")
        data["events"] = MovementEventSerializer(
            events, many=True, context=self.get_serializer_context()
        ).data
        return Response(data)

    @action(detail=True, methods=["post"])
    def reprint(self, request, pk=None):
        asset = self.get_object()
        services.reprint_label(asset, user=request.user, reason=request.data.get("reason", ""))
        return Response(self.get_serializer(asset).data)

    @action(detail=True, methods=["get"])
    def reports(self, request, pk=None):
        asset = self.get_object()
        return Response(
            InspectionReportListSerializer(
                asset.reports.select_related(
                    "asset__asset_model__manufacturer",
                    "asset__asset_model__asset_class",
                    "asset__customer",
                    "asset__lot",
                    "technician",
                ),
                many=True,
                context=self.get_serializer_context(),
            ).data
        )

    @action(detail=True, methods=["post"], url_path="new-report")
    def new_report(self, request, pk=None):
        if not has_role(request.user, *INSPECTORS):
            return Response(
                {"detail": _("You do not have permission to perform this action.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        asset = self.get_object()
        try:
            report = inspection.new_version(
                asset, user=request.user, reason=request.data.get("reason", "")
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response({"id": report.id}, status=201)

    @action(detail=True, methods=["post"])
    def disassemble(self, request, pk=None):
        """{"parts": [{"asset_model", "quantity", "serial"}], "reason"} — a scrap asset taken
        apart (inspectors)."""
        if not has_role(request.user, *INSPECTORS):
            return Response(
                {"detail": _("You do not have permission to perform this action.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        asset = self.get_object()
        parts = []
        for entry in request.data.get("parts") or []:
            model = AssetModel.objects.filter(pk=entry.get("asset_model") or 0).first()
            quantity = str(entry.get("quantity") or "1")
            if model is None or not quantity.isdigit() or int(quantity) < 1:
                return Response(
                    {"parts": [_("Choose each part's model and quantity.")]}, status=400
                )
            parts.append(
                {"asset_model": model, "quantity": int(quantity), "serial": entry.get("serial", "")}
            )
        try:
            children = inspection.disassemble(
                asset, user=request.user, parts=parts, reason=request.data.get("reason", "")
            )
        except DomainError as exc:
            return domain_error(exc)
        context = self.get_serializer_context()
        return Response(AssetSerializer(children, many=True, context=context).data, status=201)


class MovementViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """GET: the latest events (?asset=, ?container=, ?mine=true); POST {object_code,
    destination_code, reason}: move what was read to where it was read (RN-02, RN-08).
    POST <id>/reverse/ {reason}: undo an asset's latest event (supervisors)."""

    queryset = MovementEvent.objects.select_related(
        "asset",
        "container",
        "from_location",
        "to_location",
        "from_container",
        "to_container",
        "user",
    ).order_by("-at", "-id")
    serializer_class = MovementEventSerializer
    permission_classes = [role_permission(*MOVERS)]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("asset", "").isdigit():
            queryset = queryset.filter(asset_id=int(params["asset"]))
        if params.get("container", "").isdigit():
            queryset = queryset.filter(container_id=int(params["container"]))
        if params.get("mine") == "true":
            queryset = queryset.filter(user=self.request.user, parent_event__isnull=True)
        return queryset

    def create(self, request):
        serializer = MovementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            target = services.resolve_code(data["object_code"], field="object")
            destination = services.resolve_code(data["destination_code"], field="destination")
            if isinstance(target, Asset):
                if isinstance(destination, Asset):
                    raise DomainError(_("Read a location or a container."), field="destination")
                event = services.move_asset(
                    target,
                    user=request.user,
                    to_location=destination if isinstance(destination, Location) else None,
                    to_container=destination if isinstance(destination, Container) else None,
                    reason=data["reason"],
                )
            elif isinstance(target, Container):
                if not isinstance(destination, Location):
                    raise DomainError(_("A container goes to a location."), field="destination")
                event = services.move_container(
                    target, to_location=destination, user=request.user, reason=data["reason"]
                )
            else:
                raise DomainError(_("Read an asset or a container."), field="object")
        except DomainError as exc:
            return domain_error(exc)
        return Response(self.get_serializer(event).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        if not has_role(request.user, INVENTORY_SUPERVISOR):
            return Response(
                {"detail": _("You do not have permission to perform this action.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        event = self.get_object()
        try:
            reversal = services.reverse_event(
                event, user=request.user, reason=request.data.get("reason", "")
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response(self.get_serializer(reversal).data, status=status.HTTP_201_CREATED)


class LookupView(APIView):
    """GET ?code=: what a code read is (asset, container or location), its check digit verified
    (RN-15) — the movement screen shows it before the destination is read."""

    def get(self, request):
        try:
            found = services.resolve_code(request.query_params.get("code", ""))
        except DomainError as exc:
            return domain_error(exc)
        context = {"request": request}
        if isinstance(found, Asset):
            return Response({"kind": "asset", "item": AssetSerializer(found, context=context).data})
        if isinstance(found, Container):
            return Response(
                {"kind": "container", "item": ContainerSerializer(found, context=context).data}
            )
        return Response(
            {"kind": "location", "item": LocationSerializer(found, context=context).data}
        )


class LabelRangeViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Horizon IDs reserved for pre-printed labels: POST {count} reserves consecutive IDs."""

    queryset = LabelRange.objects.select_related("reserved_by")
    serializer_class = LabelRangeSerializer
    permission_classes = [role_permission(*LABELERS)]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            label_range = services.reserve_label_range(
                serializer.validated_data["count"], request.user
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response(self.get_serializer(label_range).data, status=status.HTTP_201_CREATED)


# --- Phase 2: appointments, receiving lots, occurrences, accessory balances -------------------


def _code_lookup(code: str, kinds: tuple, field: str):
    """The container or location of a code read; '' → None."""
    if not (code or "").strip():
        return None
    found = services.resolve_code(code, field=field)
    if not isinstance(found, kinds):
        raise DomainError(_("Read a location or a container."), field=field)
    return found


class AppointmentViewSet(viewsets.ModelViewSet):
    """Receivings and shipments scheduled at the warehouses' docks.

    List: ?kind=, ?warehouse=, ?status=, ?customer=, ?from=&to= (dates, for the calendar),
    ?search= (code, customer, carrier, plate), pagination. Writing: analysts and supervisors.
    `expected_items` only for analysts, supervisors and commercial (RN-17).
    POST <id>/status/ {status}: confirm, cancel, no-show, reschedule (receivings start and end
    with their lot). POST parse-expected/ {text}: rows pasted from a spreadsheet, resolved.
    """

    queryset = Appointment.objects.select_related(
        "warehouse", "customer", "carrier", "created_by", "lot"
    ).prefetch_related("expected_items__asset_model__manufacturer")
    serializer_class = AppointmentSerializer
    permission_classes = [role_permission(*SCHEDULERS)]
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "customer__name",
        "customer__trade_name",
        "carrier__name",
        "carrier_name",
        "vehicle_plate",
        "driver_name",
    ]
    ordering_fields = ["starts_at", "status", "kind"]
    ordering = ["starts_at"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["can_see_expected"] = has_role(self.request.user, *EXPECTED_READERS)
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("kind") in AppointmentKind.values:
            queryset = queryset.filter(kind=params["kind"])
        if params.get("status") in AppointmentStatus.values:
            queryset = queryset.filter(status=params["status"])
        for param in ("warehouse", "customer"):
            if params.get(param, "").isdigit():
                queryset = queryset.filter(**{f"{param}_id": int(params[param])})
        start, end = parse_date(params.get("from") or ""), parse_date(params.get("to") or "")
        if start:
            queryset = queryset.filter(ends_at__date__gte=start)
        if end:
            queryset = queryset.filter(starts_at__date__lte=end)
        search = params.get("search", "")
        match = re.fullmatch(r"\s*APT-(\d{4})-(\d+)\s*", search, re.IGNORECASE)
        if match:
            return Appointment.objects.filter(year=int(match[1]), sequence=int(match[2]))
        return queryset

    def filter_queryset(self, queryset):
        if re.fullmatch(r"\s*APT-\d{4}-\d+\s*", self.request.query_params.get("search", ""), re.I):
            return queryset
        return super().filter_queryset(queryset)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        appointment = self.get_object()
        if hasattr(appointment, "lot"):
            return Response(
                {"detail": _("This appointment has a lot: cancel it instead.")},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        appointment = self.get_object()
        try:
            appointment = receiving.set_appointment_status(
                appointment, request.data.get("status", "")
            )
        except (DomainError, KeyError) as exc:
            if isinstance(exc, KeyError):
                return Response({"status": [_("Choose a valid status.")]}, status=400)
            return domain_error(exc)
        return Response(self.get_serializer(appointment).data)

    @action(detail=False, methods=["post"], url_path="parse-expected")
    def parse_expected(self, request):
        """Rows pasted from a spreadsheet → models resolved by "Manufacturer Model" (or the
        model alone when only one manufacturer has it), with errors per row."""
        rows = parse_pasted(str(request.data.get("text", "")))
        models = list(AssetModel.objects.filter(is_enabled=True).select_related("manufacturer"))
        by_full = {model_key(f"{m.manufacturer.name} {m.name}"): m for m in models}
        by_name: dict = {}
        for m in models:
            by_name.setdefault(model_key(m.name), []).append(m)
        result = []
        for row in rows:
            errors = []
            key = model_key(row.model_text)
            model = by_full.get(key) or (
                by_name[key][0] if len(by_name.get(key, [])) == 1 else None
            )
            if model is None:
                errors.append(
                    _("Model not found: %(model)s.") % {"model": row.model_text or "—"}
                    if len(by_name.get(key, [])) < 2
                    else _("Several manufacturers have %(model)s: write the manufacturer too.")
                    % {"model": row.model_text}
                )
            if row.quantity is None:
                errors.append(_("Quantity must be a whole number from 1."))
            elif row.serial and row.quantity != 1:
                errors.append(_("A line with a serial number is one unit."))
            result.append(
                {
                    "line": row.line,
                    "asset_model": model.id if model else None,
                    "asset_model_label": f"{model.manufacturer.name} {model.name}"
                    if model
                    else row.model_text,
                    "tracking": model.tracking if model else None,
                    "serial": row.serial,
                    "quantity": row.quantity,
                    "errors": errors,
                }
            )
        return Response({"rows": result})


class ReceivingLotViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Receiving lots. List: ?status=, ?warehouse=, ?customer=, ?search= (code, customer,
    fiscal document), pagination. POST (receivers, supervisors): open a lot. Actions: units/
    (triage of a unit; multipart with "photo" when there is no serial), accessories/,
    received/, reconcile/, close/, attachments/, expected/ (not for receivers — RN-17)."""

    queryset = ReceivingLot.objects.select_related(
        "warehouse", "customer", "appointment", "dock", "opened_by", "closed_by"
    ).annotate(
        units_count=Count("assets", distinct=True),
        open_occurrences=Count(
            "occurrences", filter=Q(occurrences__status=OccurrenceStatus.OPEN), distinct=True
        ),
    )
    serializer_class = ReceivingLotSerializer
    permission_classes = [role_permission(*RECEIVERS)]
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = ["customer__name", "customer__trade_name", "fiscal_document_number"]
    ordering_fields = ["opened_at", "status", "closed_at"]
    ordering = ["-opened_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("status") in LotStatus.values:
            queryset = queryset.filter(status=params["status"])
        for param in ("warehouse", "customer"):
            if params.get(param, "").isdigit():
                queryset = queryset.filter(**{f"{param}_id": int(params[param])})
        return queryset

    def filter_queryset(self, queryset):
        match = re.fullmatch(
            r"\s*LOT-(\d{4})-(\d+)\s*", self.request.query_params.get("search", ""), re.I
        )
        if match:
            return queryset.filter(year=int(match[1]), sequence=int(match[2]))
        return super().filter_queryset(queryset)

    def _lot_data(self, lot):
        return self.get_serializer(self.get_queryset().get(pk=lot.pk)).data

    def create(self, request):
        serializer = LotOpenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            dock = services.resolve_code(data["dock_code"], field="dock")
            if not isinstance(dock, Location):
                raise DomainError(_("Read the dock where the triage happens."), field="dock")
            lot = receiving.open_lot(
                warehouse=data.get("warehouse")
                or getattr(data.get("appointment"), "warehouse", None),
                customer=data.get("customer"),
                appointment=data.get("appointment"),
                dock=dock,
                user=request.user,
                fiscal_document_number=data["fiscal_document_number"],
                notes=data["notes"],
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response(self._lot_data(lot), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def units(self, request, pk=None):
        lot = self.get_object()
        model = AssetModel.objects.filter(pk=request.data.get("asset_model") or 0).first()
        if model is None:
            return Response({"asset_model": [_("Choose a valid model.")]}, status=400)
        try:
            container = _code_lookup(
                request.data.get("container_code", ""), (Container,), "container"
            )
            asset = receiving.triage_unit(
                lot,
                user=request.user,
                asset_model=model,
                horizon_id=request.data.get("horizon_id", ""),
                serial=request.data.get("serial", ""),
                no_serial_reason=request.data.get("no_serial_reason", ""),
                container=container,
                photo=request.FILES.get("photo"),
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response(
            AssetSerializer(asset, context=self.get_serializer_context()).data, status=201
        )

    @action(detail=True, methods=["post"])
    def accessories(self, request, pk=None):
        lot = self.get_object()
        model = AssetModel.objects.filter(pk=request.data.get("asset_model") or 0).first()
        if model is None:
            return Response({"asset_model": [_("Choose a valid model.")]}, status=400)

        def number(field):
            value = str(request.data.get(field, "") or "0").strip()
            return int(value) if value.isdigit() else -1

        try:
            container = _code_lookup(
                request.data.get("container_code", ""), (Container,), "container"
            )
            scrap = _code_lookup(
                request.data.get("scrap_code", ""), (Container, Location), "scrap_destination"
            )
            receiving.triage_accessories(
                lot,
                user=request.user,
                asset_model=model,
                quantity=number("quantity"),
                container=container,
                damaged_quantity=number("damaged_quantity"),
                scrap_container=scrap if isinstance(scrap, Container) else None,
                scrap_location=scrap if isinstance(scrap, Location) else None,
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response(self._received(lot), status=201)

    def _received(self, lot) -> dict:
        context = self.get_serializer_context()
        units = lot.assets.select_related(
            "asset_model__manufacturer",
            "asset_model__asset_class",
            "current_location__warehouse",
            "current_container",
        ).order_by("-id")
        events = (
            receiving.lot_accessory_events(lot)
            .select_related("accessory_model__manufacturer", "to_location", "to_container", "user")
            .order_by("-at", "-id")
        )
        return {
            "units": AssetSerializer(units, many=True, context=context).data,
            "accessories": MovementEventSerializer(events, many=True, context=context).data,
        }

    @action(detail=True, methods=["get"])
    def received(self, request, pk=None):
        return Response(self._received(self.get_object()))

    @action(detail=True, methods=["get"])
    def expected(self, request, pk=None):
        """The expected list: never for the receivers who count (RN-17)."""
        if not has_role(request.user, *EXPECTED_READERS):
            return Response(
                {"detail": _("The expected list is not shown to whoever counts (blind count).")},
                status=status.HTTP_403_FORBIDDEN,
            )
        lot = self.get_object()
        items = (
            ExpectedItem.objects.filter(appointment_id=lot.appointment_id).select_related(
                "asset_model__manufacturer"
            )
            if lot.appointment_id
            else ExpectedItem.objects.none()
        )
        return Response(ExpectedItemSerializer(items, many=True).data)

    @action(detail=True, methods=["post"])
    def reconcile(self, request, pk=None):
        lot = self.get_object()
        try:
            receiving.reconcile_lot(lot, user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return Response(self._lot_data(lot))

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        lot = self.get_object()
        try:
            receiving.close_lot(lot, user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return Response(self._lot_data(lot))

    @action(detail=True, methods=["get", "post"])
    def attachments(self, request, pk=None):
        lot = self.get_object()
        if request.method == "POST":
            upload = request.FILES.get("file")
            if upload is None:
                return Response({"file": [_("Choose a file to upload.")]}, status=400)
            kind = request.data.get("kind", AttachmentKind.OTHER)
            if kind not in AttachmentKind.values:
                return Response({"kind": [_("Choose a valid type.")]}, status=400)
            occurrence = lot.occurrences.filter(pk=request.data.get("occurrence") or 0).first()
            try:
                receiving.add_attachment(
                    lot, kind=kind, upload=upload, user=request.user, occurrence=occurrence
                )
            except DomainError as exc:
                return domain_error(exc)
        items = lot.attachments.select_related("uploaded_by", "asset")
        return Response(
            LotAttachmentSerializer(items, many=True, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<attachment_id>\d+)")
    def delete_attachment(self, request, pk=None, attachment_id=None):
        lot = self.get_object()
        attachment = lot.attachments.filter(pk=attachment_id).first()
        if attachment is None:
            raise Http404
        if lot.status == LotStatus.CLOSED:
            return Response({"detail": _("This lot is closed.")}, status=status.HTTP_409_CONFLICT)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<attachment_id>\d+)/download")
    def download_attachment(self, request, pk=None, attachment_id=None):
        lot = self.get_object()
        attachment = lot.attachments.filter(pk=attachment_id).first()
        if attachment is None:
            raise Http404
        try:
            handle = attachment.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        inline = request.query_params.get("inline") == "1" and opens_inline(attachment.name)
        return FileResponse(
            handle,
            content_type=attachment.content_type,
            as_attachment=not inline,
            filename=attachment.name,
        )

    @action(detail=True, methods=["get", "put"], url_path="erasure-tools")
    def erasure_tools(self, request, pk=None):
        """The erasure tool and method per asset class with data storage in the lot (RN-04).
        GET: each class, its definition and the active tools serving it. PUT (supervisors):
        {"definitions": [{"asset_class", "tool", "method"}]} sets them."""
        lot = self.get_object()
        if request.method == "PUT":
            if not has_role(request.user, INVENTORY_SUPERVISOR):
                return Response(
                    {"detail": _("Only inventory supervisors define the lot's tools.")},
                    status=status.HTTP_403_FORBIDDEN,
                )
            for entry in request.data.get("definitions") or []:
                tool = ErasureTool.objects.filter(pk=entry.get("tool") or 0, is_active=True).first()
                class_id = entry.get("asset_class")
                if tool is None or not tool.asset_classes.filter(pk=class_id).exists():
                    return Response(
                        {"detail": _("Choose an active tool that serves this asset class.")},
                        status=400,
                    )
                if entry.get("method") not in tool.methods:
                    return Response({"detail": _("Choose a method of this tool.")}, status=400)
                LotErasureTool.objects.update_or_create(
                    lot=lot,
                    asset_class_id=class_id,
                    defaults={"tool": tool, "method": entry["method"], "defined_by": request.user},
                )
        classes = (
            AssetClass.objects.filter(asset_models__assets__lot=lot, asset_models__has_storage=True)
            .distinct()
            .order_by("name")
        )
        definitions = {
            d.asset_class_id: d
            for d in lot.erasure_tools.select_related("tool", "asset_class", "defined_by")
        }
        context = self.get_serializer_context()
        return Response(
            [
                {
                    "asset_class": c.id,
                    "asset_class_name": c.name,
                    "definition": LotErasureToolSerializer(definitions[c.id], context=context).data
                    if c.id in definitions
                    else None,
                    "tools": [
                        {"id": t.id, "label": str(t), "methods": t.methods}
                        for t in ErasureTool.objects.filter(is_active=True, asset_classes=c)
                    ],
                }
                for c in classes
            ]
        )


class OccurrenceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Occurrences of lots. ?lot=, ?status=, ?kind=. Receivers and supervisors register and
    resolve them; only supervisors accept them (POST <id>/accept/ {resolution})."""

    queryset = Occurrence.objects.select_related(
        "lot", "transfer", "asset", "asset_model__manufacturer", "responsible", "resolved_by"
    ).annotate(attachments_count=Count("attachments"))
    serializer_class = OccurrenceSerializer
    permission_classes = [role_permission(*RECEIVERS)]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("lot", "").isdigit():
            queryset = queryset.filter(lot_id=int(params["lot"]))
        if params.get("transfer", "").isdigit():
            queryset = queryset.filter(transfer_id=int(params["transfer"]))
        if params.get("status") in OccurrenceStatus.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("kind") in OccurrenceKind.values:
            queryset = queryset.filter(kind=params["kind"])
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _respond(self, occurrence):
        return Response(self.get_serializer(self.get_queryset().get(pk=occurrence.pk)).data)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        try:
            occurrence = receiving.resolve_occurrence(
                self.get_object(), user=request.user, resolution=request.data.get("resolution", "")
            )
        except DomainError as exc:
            return domain_error(exc)
        return self._respond(occurrence)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        if not has_role(request.user, INVENTORY_SUPERVISOR):
            return Response(
                {"detail": _("Only inventory supervisors accept occurrences.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            occurrence = receiving.accept_occurrence(
                self.get_object(), user=request.user, resolution=request.data.get("resolution", "")
            )
        except DomainError as exc:
            return domain_error(exc)
        return self._respond(occurrence)


class AccessoryBalanceViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Accessory balances (models tracked by quantity) with something left.
    ?asset_model=, ?warehouse=, ?condition=, ?search= (model, manufacturer, container,
    location)."""

    queryset = AccessoryBalance.objects.filter(quantity__gt=0).select_related(
        "asset_model__manufacturer",
        "asset_model__asset_class",
        "container__current_location__warehouse",
        "location__warehouse",
    )
    serializer_class = AccessoryBalanceSerializer
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "asset_model__name",
        "asset_model__manufacturer__name",
        "container__code",
        "location__code",
    ]
    ordering_fields = ["asset_model__name", "quantity", "condition"]
    ordering = ["asset_model__name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("asset_model", "").isdigit():
            queryset = queryset.filter(asset_model_id=int(params["asset_model"]))
        if params.get("condition") in AccessoryCondition.values:
            queryset = queryset.filter(condition=params["condition"])
        if params.get("warehouse", "").isdigit():
            warehouse = int(params["warehouse"])
            queryset = queryset.filter(
                Q(location__warehouse_id=warehouse)
                | Q(container__current_location__warehouse_id=warehouse)
            )
        return queryset


# --- Phase 3: grades, penalty table, erasure tools, inspection ---------------------------------


def _upload(request, field="file"):
    upload = request.FILES.get(field)
    if upload is None:
        raise DomainError(_("Choose a file to upload."), field=field)
    return upload


def _file_response(file_field, name, content_type, inline):
    try:
        handle = file_field.open("rb")
    except (FileNotFoundError, ValueError) as exc:
        raise Http404 from exc
    return FileResponse(
        handle,
        content_type=content_type,
        as_attachment=not (inline and opens_inline(name)),
        filename=name,
    )


class GradeLevelViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """The meanings of the grade levels (codes are fixed). Supervisors edit them."""

    queryset = GradeLevel.objects.all()
    serializer_class = GradeLevelSerializer
    permission_classes = [role_permission(*SUPERVISORS)]
    pagination_class = None


class PenaltyRateViewSet(viewsets.ModelViewSet):
    """The penalty table (asset class × kind of finding, with validity; no overlaps — RN-03).
    ?asset_class=, ?finding_kind=, ?current=true (valid today), ?search= (asset class)."""

    queryset = PenaltyRate.objects.select_related("asset_class")
    serializer_class = PenaltyRateSerializer
    permission_classes = [role_permission(*SUPERVISORS)]
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = ["asset_class__name"]
    ordering_fields = ["asset_class__name", "finding_kind", "value", "valid_from", "valid_to"]
    ordering = ["asset_class__name", "finding_kind", "-valid_from"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("asset_class", "").isdigit():
            queryset = queryset.filter(asset_class_id=int(params["asset_class"]))
        if params.get("finding_kind") in FindingKind.values:
            queryset = queryset.filter(finding_kind=params["finding_kind"])
        if params.get("current") == "true":
            today = timezone.localdate()
            queryset = queryset.filter(valid_from__lte=today).filter(
                Q(valid_to__isnull=True) | Q(valid_to__gte=today)
            )
        return queryset


class ErasureToolViewSet(RefuseDeletingWhenInUse, viewsets.ModelViewSet):
    """Data erasure tools. ?asset_class= (tools serving it), ?is_active=, ?search=."""

    queryset = ErasureTool.objects.prefetch_related("asset_classes")
    serializer_class = ErasureToolSerializer
    permission_classes = [role_permission(*SUPERVISORS)]
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = ["name", "version", "asset_classes__name"]
    ordering_fields = ["name", "version", "is_active"]
    ordering = ["name", "version"]
    in_use_message = gettext_noop(
        "This tool was used in lots or certificates and cannot be deleted. Deactivate it instead."
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("asset_class", "").isdigit():
            queryset = queryset.filter(asset_classes__id=int(params["asset_class"]))
        if params.get("is_active") in ("true", "false"):
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        return queryset.distinct()


class InspectionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Inspection reports. List: ?status=, ?asset=, ?mine=true (started by me), ?search=
    (Horizon ID, serial, model). The draft is edited with PATCH; actions below. Inspectors
    (technicians, supervisors) prepare them; supervisors approve; commercial marks sent."""

    queryset = InspectionReport.objects.select_related(
        "asset__asset_model__manufacturer",
        "asset__asset_model__asset_class",
        "asset__customer",
        "asset__lot",
        "asset__current_location__warehouse",
        "asset__current_container",
        "technician",
        "approved_by",
    ).prefetch_related("photos", "findings")
    permission_classes = [role_permission(*INSPECTORS)]
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = ["asset__horizon_id", "asset__serial", "asset__asset_model__name"]
    ordering_fields = ["started_at", "finished_at", "approved_at", "version"]
    ordering = ["-started_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return InspectionReportListSerializer
        return InspectionReportSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("status") in ReportStatus.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("asset", "").isdigit():
            queryset = queryset.filter(asset_id=int(params["asset"]))
        if params.get("mine") == "true":
            queryset = queryset.filter(technician=self.request.user)
        return queryset

    def _report(self, report):
        return Response(
            InspectionReportSerializer(
                self.get_queryset().get(pk=report.pk), context=self.get_serializer_context()
            ).data
        )

    def perform_update(self, serializer):
        inspection.lock_draft(serializer.instance)
        serializer.save()
        inspection.sync_report(serializer.instance)

    def update(self, request, *args, **kwargs):
        try:
            super().update(request, *args, **kwargs)
        except DomainError as exc:
            return domain_error(exc)
        return self._report(self.get_object())

    def _do(self, call):
        try:
            return call()
        except DomainError as exc:
            return domain_error(exc)

    @action(detail=False, methods=["post"])
    def start(self, request):
        def run():
            asset = services.resolve_code(request.data.get("asset_code", ""), field="asset")
            bench = services.resolve_code(request.data.get("bench_code", ""), field="bench")
            if not isinstance(asset, Asset):
                raise DomainError(_("Read the asset's label."), field="asset")
            if not isinstance(bench, Location):
                raise DomainError(_("Read an active bench."), field="bench")
            report = inspection.start_inspection(asset, bench=bench, user=request.user)
            return self._report(report)

        return self._do(run)

    @action(detail=True, methods=["post"])
    def serial(self, request, pk=None):
        report = self.get_object()
        return self._do(
            lambda: (
                inspection.complete_serial(report, request.data.get("serial", "")),
                self._report(report),
            )[1]
        )

    @action(detail=True, methods=["post"])
    def specs(self, request, pk=None):
        report = self.get_object()
        values = request.data.get("specs") or {}
        if not isinstance(values, dict):
            return Response({"specs": [_("Enter the values by field.")]}, status=400)
        return self._do(lambda: (inspection.set_specs(report, values), self._report(report))[1])

    @action(detail=True, methods=["get", "post"])
    def photos(self, request, pk=None):
        report = self.get_object()
        if request.method == "POST":
            kind = request.data.get("kind", "")
            if kind not in PhotoKind.values:
                return Response({"kind": [_("Choose a valid type.")]}, status=400)
            result = self._do(
                lambda: inspection.add_photo(
                    report,
                    kind=kind,
                    upload=_upload(request),
                    user=request.user,
                    description=request.data.get("description", ""),
                )
            )
            if isinstance(result, Response):
                return result
        return Response(ReportPhotoSerializer(report.photos.all(), many=True).data)

    @action(detail=True, methods=["delete"], url_path=r"photos/(?P<photo_id>\d+)")
    def delete_photo(self, request, pk=None, photo_id=None):
        report = self.get_object()
        photo = report.photos.filter(pk=photo_id).first()
        if photo is None:
            raise Http404
        if report.status != ReportStatus.DRAFT:
            return Response({"detail": _("Only a draft report can be changed.")}, status=409)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path=r"photos/(?P<photo_id>\d+)/file")
    def photo_file(self, request, pk=None, photo_id=None):
        photo = self.get_object().photos.filter(pk=photo_id).first()
        if photo is None:
            raise Http404
        return _file_response(photo.file, photo.name, photo.content_type, inline=True)

    @action(detail=True, methods=["post"])
    def findings(self, request, pk=None):
        report = self.get_object()
        serializer = FindingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def run():
            inspection.lock_draft(report)
            serializer.save(report=report)
            inspection.apply_values(report)
            return self._report(report)

        return self._do(run)

    @action(detail=True, methods=["patch", "delete"], url_path=r"findings/(?P<finding_id>\d+)")
    def finding(self, request, pk=None, finding_id=None):
        report = self.get_object()
        finding = report.findings.filter(pk=finding_id).first()
        if finding is None:
            raise Http404
        if "value" in request.data or "value_justification" in request.data:
            # Only supervisors set a value (null: back to the table's)
            if not has_role(request.user, INVENTORY_SUPERVISOR):
                return Response(
                    {"detail": _("Only inventory supervisors change a finding's value.")},
                    status=status.HTTP_403_FORBIDDEN,
                )
            raw = request.data.get("value")
            try:
                value = None if raw in (None, "") else Decimal(str(raw))
            except (InvalidOperation, ValueError):
                return Response({"value": [_("Enter a number.")]}, status=400)
            return self._do(
                lambda: (
                    inspection.set_finding_value(
                        finding,
                        value=value,
                        justification=request.data.get("value_justification", ""),
                    ),
                    self._report(report),
                )[1]
            )

        def run():
            inspection.lock_draft(report)
            if request.method == "DELETE":
                if finding.automatic:
                    raise DomainError(
                        _("Automatic findings follow the kit and the cleaning."), field="finding"
                    )
                finding.delete()
            else:
                serializer = FindingSerializer(finding, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
                inspection.apply_values(report)
            return self._report(report)

        return self._do(run)

    @action(detail=True, methods=["post"])
    def certificates(self, request, pk=None):
        report = self.get_object()
        disk_model = AssetModel.objects.filter(pk=request.data.get("disk_model") or 0).first()
        return self._do(
            lambda: (
                inspection.add_certificate(
                    report,
                    user=request.user,
                    result=request.data.get("result", ""),
                    disk_serial=request.data.get("disk_serial", ""),
                    upload=request.FILES.get("file"),
                    disk_model=disk_model,
                ),
                self._report(report),
            )[1]
        )

    @action(detail=True, methods=["get"], url_path=r"certificates/(?P<certificate_id>\d+)/file")
    def certificate_file(self, request, pk=None, certificate_id=None):
        report = self.get_object()
        certificate = report.asset.erasures.filter(pk=certificate_id).first()
        if certificate is None or not certificate.file:
            raise Http404
        return _file_response(
            certificate.file,
            certificate.name,
            content_type_for(certificate.name),
            inline=request.query_params.get("inline") == "1",
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        report = self.get_object()
        return self._do(lambda: self._report(inspection.submit(report, user=request.user)))

    def _supervisor(self, request):
        if not has_role(request.user, INVENTORY_SUPERVISOR):
            return Response(
                {"detail": _("Only inventory supervisors approve reports.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @action(detail=True, methods=["post"], url_path="return")
    def send_back(self, request, pk=None):
        refused = self._supervisor(request)
        if refused:
            return refused
        report = self.get_object()
        return self._do(
            lambda: self._report(
                inspection.return_to_draft(
                    report, user=request.user, notes=request.data.get("notes", "")
                )
            )
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        refused = self._supervisor(request)
        if refused:
            return refused
        report = self.get_object()
        return self._do(lambda: self._report(inspection.approve(report, user=request.user)))

    @action(detail=True, methods=["post"], permission_classes=[role_permission(*SENDERS)])
    def sent(self, request, pk=None):
        report = self.get_object()
        return self._do(lambda: self._report(inspection.mark_sent(report, user=request.user)))


# --- Phase 4: deadlines, holidays, blocks, disputes, charges, alerts ----------------------------


class DeadlineSettingViewSet(
    mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """The deadlines (block release, dispute, dispute analysis). Supervisors edit them."""

    queryset = DeadlineSetting.objects.all()
    serializer_class = DeadlineSettingSerializer
    permission_classes = [role_permission(*SUPERVISORS)]
    pagination_class = None


class AgingLimitViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Days an asset may stay in each status before an alert (empty: none)."""

    queryset = AgingLimit.objects.all()
    serializer_class = AgingLimitSerializer
    permission_classes = [role_permission(*SUPERVISORS)]
    pagination_class = None


class HolidayViewSet(viewsets.ModelViewSet):
    """Holidays (not business days). ?year=."""

    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [role_permission(*SUPERVISORS)]
    ordering = ["date"]

    def get_queryset(self):
        queryset = super().get_queryset()
        year = self.request.query_params.get("year", "")
        return queryset.filter(date__year=int(year)) if year.isdigit() else queryset


class DeadlineCheckView(APIView):
    """POST: run the daily routine now (supervisors)."""

    permission_classes = [role_permission(*SUPERVISORS, read_for_all=False)]

    def post(self, request):
        return Response(followups.check_deadlines())


def _evidence(request, *, followup=None, dispute=None):
    try:
        followups.add_evidence(
            upload=_upload(request), user=request.user, followup=followup, dispute=dispute
        )
    except DomainError as exc:
        return domain_error(exc)
    return None


class BlockFollowUpViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Access blocks to be released by customers. ?status=, ?customer=, ?lot=, ?search=
    (Horizon ID, serial, customer). Actions: notify (POST {ids}; commercial, supervisors),
    report-release (commercial, supervisors), check (POST {released}; inspectors), decide
    (POST {decision, notes}; supervisors), evidence (GET/POST multipart)."""

    queryset = BlockFollowUp.objects.select_related(
        "asset__asset_model__manufacturer",
        "asset__customer",
        "asset__lot",
        "asset__current_location",
        "finding",
        "checked_by",
        "decided_by",
    ).prefetch_related("evidence")
    serializer_class = BlockFollowUpSerializer
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "asset__horizon_id",
        "asset__serial",
        "asset__customer__name",
        "asset__customer__trade_name",
    ]
    ordering_fields = ["due_date", "created_at", "status"]
    ordering = ["due_date", "id"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("status") in BlockStatus.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("customer", "").isdigit():
            queryset = queryset.filter(asset__customer_id=int(params["customer"]))
        if params.get("lot", "").isdigit():
            queryset = queryset.filter(asset__lot_id=int(params["lot"]))
        return queryset

    def _respond(self, followup):
        return Response(self.get_serializer(self.get_queryset().get(pk=followup.pk)).data)

    def _guard(self, request, *keys):
        if not has_role(request.user, *keys):
            return Response(
                {"detail": _("You do not have permission to perform this action.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @action(detail=False, methods=["post"])
    def notify(self, request):
        refused = self._guard(request, *SENDERS)
        if refused:
            return refused
        ids = [i for i in request.data.get("ids") or [] if str(i).isdigit()]
        try:
            done = followups.mark_notified(
                list(BlockFollowUp.objects.filter(pk__in=ids)), user=request.user
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response(
            self.get_serializer(
                self.get_queryset().filter(pk__in=[f.pk for f in done]), many=True
            ).data
        )

    @action(detail=True, methods=["post"], url_path="report-release")
    def report_release(self, request, pk=None):
        refused = self._guard(request, *SENDERS)
        if refused:
            return refused
        try:
            return self._respond(followups.report_release(self.get_object(), user=request.user))
        except DomainError as exc:
            return domain_error(exc)

    @action(detail=True, methods=["post"])
    def check(self, request, pk=None):
        refused = self._guard(request, *INSPECTORS)
        if refused:
            return refused
        try:
            followup = followups.check_release(
                self.get_object(), user=request.user, released=bool(request.data.get("released"))
            )
        except DomainError as exc:
            return domain_error(exc)
        return self._respond(followup)

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        refused = self._guard(request, *SUPERVISORS)
        if refused:
            return refused
        try:
            followup = followups.decide_expired(
                self.get_object(),
                user=request.user,
                decision=request.data.get("decision", ""),
                notes=request.data.get("notes", ""),
            )
        except DomainError as exc:
            return domain_error(exc)
        return self._respond(followup)

    @action(detail=True, methods=["get", "post"])
    def evidence(self, request, pk=None):
        followup = self.get_object()
        if request.method == "POST":
            refused = self._guard(request, *SENDERS, *INSPECTORS)
            if refused:
                return refused
            error = _evidence(request, followup=followup)
            if error:
                return error
        return Response(EvidenceSerializer(followup.evidence.all(), many=True).data)

    @action(detail=True, methods=["get"], url_path=r"evidence/(?P<evidence_id>\d+)/file")
    def evidence_file(self, request, pk=None, evidence_id=None):
        item = self.get_object().evidence.filter(pk=evidence_id).first()
        if item is None:
            raise Http404
        return _file_response(item.file, item.name, item.content_type, inline=True)


class DisputeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Disputes of reports. ?status=, ?search= (Horizon ID, customer). POST (commercial,
    supervisors) {report, findings, justification}. analyze/ and decide/ {decision, notes,
    upheld_findings, reinspected} by supervisors other than the report's technician (RN-14);
    evidence (GET/POST multipart)."""

    queryset = Dispute.objects.select_related(
        "report__asset__asset_model__manufacturer",
        "report__asset__customer",
        "report__asset__lot",
        "report__asset__current_location",
        "registered_by",
        "analyst",
    ).prefetch_related("findings", "evidence")
    serializer_class = DisputeSerializer
    filter_backends = [filters.SearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "report__asset__horizon_id",
        "report__asset__customer__name",
        "report__asset__customer__trade_name",
    ]
    ordering_fields = ["registered_at", "analysis_due", "status"]
    ordering = ["-registered_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("status") in DisputeStatus.values:
            queryset = queryset.filter(status=self.request.query_params["status"])
        return queryset

    def _respond(self, dispute, code=200):
        return Response(
            self.get_serializer(self.get_queryset().get(pk=dispute.pk)).data, status=code
        )

    def create(self, request):
        if not has_role(request.user, *SENDERS):
            return Response(
                {"detail": _("You do not have permission to perform this action.")}, status=403
            )
        report = InspectionReport.objects.filter(pk=request.data.get("report") or 0).first()
        if report is None:
            return Response({"report": [_("Choose a valid report.")]}, status=400)
        ids = [int(i) for i in request.data.get("findings") or [] if str(i).isdigit()]
        try:
            dispute = followups.register_dispute(
                report,
                user=request.user,
                findings=list(Finding.objects.filter(pk__in=ids)) if ids else [],
                justification=request.data.get("justification", ""),
            )
        except DomainError as exc:
            return domain_error(exc)
        return self._respond(dispute, 201)

    def _supervisor(self, request):
        if not has_role(request.user, INVENTORY_SUPERVISOR):
            return Response(
                {"detail": _("Only inventory supervisors analyse disputes.")}, status=403
            )
        return None

    @action(detail=True, methods=["post"])
    def analyze(self, request, pk=None):
        refused = self._supervisor(request)
        if refused:
            return refused
        try:
            return self._respond(followups.start_analysis(self.get_object(), user=request.user))
        except DomainError as exc:
            return domain_error(exc)

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        refused = self._supervisor(request)
        if refused:
            return refused
        ids = [int(i) for i in request.data.get("upheld_findings") or [] if str(i).isdigit()]
        try:
            dispute = followups.decide_dispute(
                self.get_object(),
                user=request.user,
                decision=request.data.get("decision", ""),
                notes=request.data.get("notes", ""),
                upheld_findings=list(Finding.objects.filter(pk__in=ids)),
                reinspected=bool(request.data.get("reinspected")),
            )
        except DomainError as exc:
            return domain_error(exc)
        return self._respond(dispute)

    @action(detail=True, methods=["get", "post"])
    def evidence(self, request, pk=None):
        dispute = self.get_object()
        if request.method == "POST":
            if not has_role(request.user, *SENDERS):
                return Response(
                    {"detail": _("You do not have permission to perform this action.")}, status=403
                )
            error = _evidence(request, dispute=dispute)
            if error:
                return error
        return Response(EvidenceSerializer(dispute.evidence.all(), many=True).data)

    @action(detail=True, methods=["get"], url_path=r"evidence/(?P<evidence_id>\d+)/file")
    def evidence_file(self, request, pk=None, evidence_id=None):
        item = self.get_object().evidence.filter(pk=evidence_id).first()
        if item is None:
            raise Http404
        return _file_response(item.file, item.name, item.content_type, inline=True)


class ChargeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Findings to charge customers: ?status=chargeable (default) | charged, ?customer=,
    ?search=. POST <id>/charged/ (commercial, supervisors): the penalty was charged."""

    queryset = Finding.objects.select_related(
        "report__asset__asset_model__manufacturer",
        "report__asset__customer",
        "report__asset__lot",
        "report__asset__current_location",
    )
    serializer_class = ChargeFindingSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = [
        "report__asset__horizon_id",
        "report__asset__customer__name",
        "report__asset__customer__trade_name",
    ]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        wanted = params.get("status", FindingStatus.CHARGEABLE)
        queryset = queryset.filter(
            status=wanted
            if wanted in (FindingStatus.CHARGEABLE, FindingStatus.CHARGED)
            else FindingStatus.CHARGEABLE
        )
        if params.get("customer", "").isdigit():
            queryset = queryset.filter(report__asset__customer_id=int(params["customer"]))
        return queryset.order_by("report__asset__customer__name", "id")

    @action(detail=True, methods=["post"])
    def charged(self, request, pk=None):
        if not has_role(request.user, *SENDERS):
            return Response(
                {"detail": _("You do not have permission to perform this action.")}, status=403
            )
        try:
            finding = followups.mark_charged(self.get_object(), user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return Response(self.get_serializer(finding).data)


class AlertViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """The signed-in user's alerts (for them or one of their roles; administrators: all).
    ?unread=true. POST <id>/read/, POST read-all/."""

    serializer_class = AlertSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Alert.objects.all()
        if not is_administrator(user):
            keys = list(user.roles.exclude(key="").values_list("key", flat=True))
            queryset = queryset.filter(Q(user=user) | Q(role_key__in=keys, user__isnull=True))
        queryset = queryset.annotate(
            read=Exists(
                Alert.read_by.through.objects.filter(alert_id=OuterRef("pk"), user_id=user.pk)
            )
        )
        if self.request.query_params.get("unread") == "true":
            queryset = queryset.filter(read=False)
        return queryset.order_by("-created_at", "-id")

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        self.get_object().read_by.add(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        for alert in self.get_queryset().filter(read=False):
            alert.read_by.add(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def count(self, request):
        return Response({"unread": self.get_queryset().filter(read=False).count()})


# --- Phase 5: stock query and disposals ------------------------------------------------------


def stock_queryset(params):
    """Assets of the stock query. ?status= (default available; "all" = every status but written
    off), ?warehouse=, ?customer=, ?asset_class=, ?asset_model=, ?grade=, ?min_days= /
    ?max_days= (days since the entry), ?search= (Horizon ID, serial, model, manufacturer)."""
    queryset = Asset.objects.exclude(status=AssetStatus.WRITTEN_OFF)
    wanted = params.get("status") or AssetStatus.AVAILABLE
    if wanted in AssetStatus.values:
        queryset = queryset.filter(status=wanted)
    for param, lookup in (
        ("warehouse", "current_location__warehouse_id"),
        ("customer", "customer_id"),
        ("asset_class", "asset_model__asset_class_id"),
        ("asset_model", "asset_model_id"),
    ):
        if params.get(param, "").isdigit():
            queryset = queryset.filter(**{lookup: int(params[param])})
    if "grade" in params:
        queryset = queryset.filter(condition_grade=params["grade"].strip().upper())
    today = timezone.localdate()
    if params.get("min_days", "").isdigit():
        queryset = queryset.filter(
            created_at__date__lte=today - timedelta(days=int(params["min_days"]))
        )
    if params.get("max_days", "").isdigit():
        queryset = queryset.filter(
            created_at__date__gte=today - timedelta(days=int(params["max_days"]))
        )
    search = " ".join(params.get("search", "").split())
    if search:
        queryset = queryset.filter(
            Q(horizon_id__icontains=search)
            | Q(serial__icontains=search)
            | Q(asset_model__name__icontains=search)
            | Q(asset_model__manufacturer__name__icontains=search)
        )
    return queryset


class StockView(APIView):
    """GET: the stock grouped by asset class × model × grade × status × warehouse — units, the
    oldest entry and the average days in stock (filters: see stock_queryset)."""

    def get(self, request):
        rows = (
            stock_queryset(request.query_params)
            .values(
                "asset_model__asset_class_id",
                "asset_model_id",
                "condition_grade",
                "status",
                "current_location__warehouse_id",
            )
            .annotate(units=Count("id"), oldest=Min("created_at"))
            .order_by()
        )
        rows = list(rows)
        models = AssetModel.objects.select_related("manufacturer", "asset_class").in_bulk(
            {r["asset_model_id"] for r in rows}
        )
        warehouses = Warehouse.objects.in_bulk({r["current_location__warehouse_id"] for r in rows})
        ages = {}
        today = timezone.localdate()
        for key in stock_queryset(request.query_params).values_list(
            "asset_model_id",
            "condition_grade",
            "status",
            "current_location__warehouse_id",
            "created_at",
        ):
            ages.setdefault(key[:4], []).append((today - timezone.localtime(key[4]).date()).days)
        result = []
        for row in rows:
            model = models[row["asset_model_id"]]
            warehouse = warehouses[row["current_location__warehouse_id"]]
            key = (row["asset_model_id"], row["condition_grade"], row["status"], warehouse.pk)
            days = ages.get(key, [0])
            result.append(
                {
                    "asset_class": model.asset_class_id,
                    "asset_class_name": asset_class_name(model.asset_class),
                    "asset_model": model.pk,
                    "model": f"{model.manufacturer.name} {model.name}",
                    "grade": row["condition_grade"],
                    "status": row["status"],
                    "warehouse": warehouse.pk,
                    "warehouse_code": warehouse.code,
                    "units": row["units"],
                    "oldest_entry": row["oldest"],
                    "average_days": round(sum(days) / len(days)),
                    "max_days": max(days),
                }
            )
        result.sort(key=lambda r: (r["asset_class_name"].lower(), r["model"].lower(), r["grade"]))
        return Response(result)


class StockAssetViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET stock/assets/: the units of the stock query (same filters), each with its current
    report's data — functioning, conservation, completeness, missing items, entry date, days
    in stock (for pricing, spec §11) — and the open disposal it is in."""

    serializer_class = StockAssetSerializer
    ordering = ["created_at"]

    def get_queryset(self):
        return (
            stock_queryset(self.request.query_params)
            .select_related(
                "asset_model__manufacturer",
                "asset_model__asset_class",
                "current_location__warehouse",
                "customer",
                "lot",
            )
            .prefetch_related(
                Prefetch(
                    "reports",
                    queryset=InspectionReport.objects.filter(is_current=True),
                    to_attr="current_reports",
                ),
                Prefetch(
                    "disposal_items",
                    queryset=DisposalItem.objects.filter(
                        disposal__status__in=OPEN_DISPOSAL
                    ).select_related("disposal"),
                    to_attr="open_disposal_items",
                ),
            )
            .order_by("created_at", "id")
        )


class DisposalViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Disposals (relocation, sales, discard; parts are recorded by taking scrap apart).

    List: ?status=, ?kind=, ?warehouse=, ?customer=, ?search= (code "DSP-2026-0001", customer,
    provider, document number, keywords), pagination. Never deleted (cancel instead).
    Commercial, analysts and supervisors create, change the header, add/remove items
    (items/: {codes: [...], unit_value} or {accessory_model, quantity, condition, unit_value};
    items/<id>/ PATCH {unit_value} / DELETE) and cancel ({reason}). Storekeepers and
    supervisors pick (pick/: {code, shipping_location} or {item, code, quantity}) and ship.
    files/ (GET, POST multipart kind + file), files/<id>/ DELETE, files/<id>/file GET.
    """

    queryset = Disposal.objects.select_related(
        "warehouse",
        "customer",
        "discard_provider",
        "appointment",
        "created_by",
        "shipped_by",
        "cancelled_by",
    ).annotate(
        items_count=Count("items", distinct=True),
        picked_count=Count(
            "items", filter=Q(items__picked_quantity__gte=F("items__quantity")), distinct=True
        ),
    )
    serializer_class = DisposalSerializer
    permission_classes = [role_permission(*DISPOSERS)]
    filter_backends = [KeywordSearchFilter, NullsLastOrderingFilter]
    search_fields = [
        "customer__name",
        "customer__trade_name",
        "discard_provider__name",
        "discard_provider__trade_name",
        "document_number",
        "contract",
    ]
    ordering_fields = ["created_at", "status", "kind", "shipped_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ("pick", "ship"):
            return [role_permission(*PICKERS)()]
        if self.action == "files":
            return [role_permission(*DISPOSERS, *PICKERS)()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("status") == "open":
            queryset = queryset.filter(status__in=OPEN_DISPOSAL)
        elif params.get("status") in DisposalStatus.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("kind") in DisposalKind.values:
            queryset = queryset.filter(kind=params["kind"])
        for param in ("warehouse", "customer"):
            if params.get(param, "").isdigit():
                queryset = queryset.filter(**{f"{param}_id": int(params[param])})
        return queryset

    def filter_queryset(self, queryset):
        match = re.fullmatch(
            r"\s*DSP-(\d{4})-(\d+)\s*", self.request.query_params.get("search", ""), re.I
        )
        if match:
            return queryset.filter(year=int(match[1]), sequence=int(match[2])).order_by("id")
        return super().filter_queryset(queryset)

    def _detail(self, disposal, code=200):
        disposal = self.get_queryset().get(pk=disposal.pk)
        context = self.get_serializer_context()
        data = self.get_serializer(disposal).data
        items = disposal.items.select_related(
            "asset__asset_model__manufacturer",
            "asset__asset_model__asset_class",
            "asset__customer",
            "asset__lot",
            "asset__current_location",
            "accessory_model__manufacturer",
            "picked_by",
        )
        data["items"] = DisposalItemSerializer(items, many=True, context=context).data
        data["files"] = DisposalFileSerializer(
            disposal.files.select_related("uploaded_by"), many=True, context=context
        ).data
        data["totals"] = disposals.totals(disposal)
        data["problems"] = (
            [str(p) for p in disposals.problems(disposal)]
            if disposal.status in OPEN_DISPOSAL
            else []
        )
        return Response(data, status=code)

    def retrieve(self, request, *args, **kwargs):
        return self._detail(self.get_object())

    def _header(self, data, *, partial):
        serializer = self.get_serializer(data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def create(self, request, *args, **kwargs):
        values = self._header(request.data, partial=False)
        try:
            disposal = disposals.create(
                kind=values.get("kind", ""),
                warehouse=values["warehouse"],
                user=request.user,
                customer=values.get("customer"),
                contract=values.get("contract", ""),
                discard_provider=values.get("discard_provider"),
                appointment=values.get("appointment"),
                notes=values.get("notes", ""),
                keywords=values.get("keywords"),
            )
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(disposal, 201)

    def update(self, request, *args, **kwargs):
        disposal = self.get_object()
        values = self._header(request.data, partial=True)
        allowed = {
            "customer",
            "contract",
            "discard_provider",
            "appointment",
            "document_number",
            "notes",
            "keywords",
        }
        try:
            disposals.update_header(disposal, **{k: v for k, v in values.items() if k in allowed})
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(disposal)

    @action(detail=True, methods=["post"])
    def items(self, request, pk=None):
        disposal = self.get_object()
        try:
            value = _money(request.data.get("unit_value"))
            if request.data.get("accessory_model"):
                model = AssetModel.objects.filter(pk=request.data["accessory_model"]).first()
                if model is None:
                    raise DomainError(_("Choose a valid model."), field="accessory_model")
                disposals.add_accessory(
                    disposal,
                    model,
                    int(request.data.get("quantity") or 0),
                    user=request.user,
                    condition=request.data.get("condition") or AccessoryCondition.GOOD,
                    unit_value=value,
                )
            else:
                codes = request.data.get("codes") or []
                if not codes:
                    raise DomainError(_("Read the asset's ID."), field="code")
                with transaction.atomic():
                    for code in codes:
                        asset = _read(code, Asset, "code", _("Read the asset's ID."))
                        disposals.add_asset(disposal, asset, user=request.user, unit_value=value)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(disposal)

    @action(detail=True, methods=["patch", "delete"], url_path=r"items/(?P<item_id>\d+)")
    def item(self, request, pk=None, item_id=None):
        disposal = self.get_object()
        item = disposal.items.filter(pk=item_id).first()
        if item is None:
            raise Http404
        try:
            if request.method == "DELETE":
                disposals.remove_item(item, user=request.user)
            else:
                disposals.set_unit_value(item, _money(request.data.get("unit_value")))
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(disposal)

    @action(detail=True, methods=["post"])
    def pick(self, request, pk=None):
        disposal = self.get_object()
        try:
            code = str(request.data.get("code") or "")
            if request.data.get("item"):
                item = disposal.items.filter(pk=request.data["item"]).first()
                if item is None:
                    raise DomainError(_("Choose an item of the list."), field="item")
                place = _read(
                    code,
                    (Container, Location),
                    "code",
                    _("Read the container or location the accessories are taken from."),
                )
                disposals.pick_accessory(
                    disposal,
                    item,
                    int(request.data.get("quantity") or 0),
                    user=request.user,
                    container=place if isinstance(place, Container) else None,
                    location=place if isinstance(place, Location) else None,
                )
            else:
                shipping = _read(
                    request.data.get("shipping_location"),
                    Location,
                    "shipping_location",
                    _("Read the shipping area first."),
                )
                asset = _read(code, Asset, "code", _("Read the asset's ID."))
                disposals.pick_asset(disposal, asset, shipping_location=shipping, user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(disposal)

    @action(detail=True, methods=["post"])
    def ship(self, request, pk=None):
        disposal = self.get_object()
        try:
            disposals.ship(disposal, user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(disposal)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        disposal = self.get_object()
        try:
            disposals.cancel(disposal, user=request.user, reason=request.data.get("reason", ""))
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(disposal)

    @action(detail=True, methods=["get", "post"])
    def files(self, request, pk=None):
        disposal = self.get_object()
        if request.method == "POST":
            try:
                disposals.add_file(
                    disposal,
                    kind=request.data.get("kind", ""),
                    upload=_upload(request),
                    user=request.user,
                )
            except DomainError as exc:
                return domain_error(exc)
        return Response(
            DisposalFileSerializer(
                disposal.files.select_related("uploaded_by"),
                many=True,
                context=self.get_serializer_context(),
            ).data
        )

    @action(detail=True, methods=["delete"], url_path=r"files/(?P<file_id>\d+)")
    def file_delete(self, request, pk=None, file_id=None):
        item = self.get_object().files.filter(pk=file_id).first()
        if item is None:
            raise Http404
        try:
            disposals.remove_file(item)
        except DomainError as exc:
            return domain_error(exc)
        return Response(status=204)

    @action(detail=True, methods=["get"], url_path=r"files/(?P<file_id>\d+)/file")
    def file_download(self, request, pk=None, file_id=None):
        item = self.get_object().files.filter(pk=file_id).first()
        if item is None:
            raise Http404
        return _file_response(item.file, item.name, item.content_type, inline=True)


def _read(code, kind, field: str, message):
    """The object of a code read, of the expected kind (required)."""
    if not str(code or "").strip():
        raise DomainError(message, field=field)
    found = services.resolve_code(str(code), field=field)
    if not isinstance(found, kind):
        raise DomainError(message, field=field)
    return found


def _money(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise DomainError(_("Enter a valid value."), field="unit_value") from exc
    if not amount.is_finite():
        raise DomainError(_("Enter a valid value."), field="unit_value")
    return amount.quantize(Decimal("0.01"))


# --- Phase 6: transfers --------------------------------------------------------------------------


class TransferViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Transfers between warehouses. List: ?status= (also `open`), ?origin=, ?destination=,
    ?warehouse= (either), ?search= (code "TRF-2026-0001", reason, fiscal document, keywords).
    Never deleted (cancel before sending). Analysts and supervisors request (POST), change the
    header, add/remove items (items/: {code} — an asset or a container — or {accessory_model,
    quantity, condition}; items/<id>/ DELETE) and cancel ({reason}); supervisors approve.
    Storekeepers, receivers and supervisors pick (pick/: {code} or {item, code, quantity}),
    send, receive (receive/: {location, code, damaged, note} or {item, code, quantity}) and
    finish. files/ (GET, POST multipart kind + file), files/<id>/ DELETE, files/<id>/file GET.
    """

    queryset = Transfer.objects.select_related(
        "origin",
        "destination",
        "requested_by",
        "approved_by",
        "sent_by",
        "received_by",
        "cancelled_by",
    ).annotate(
        items_count=Count("items", distinct=True),
        picked_count=Count(
            "items", filter=Q(items__picked_quantity__gte=F("items__quantity")), distinct=True
        ),
        received_count=Count(
            "items", filter=Q(items__received_quantity__gte=F("items__quantity")), distinct=True
        ),
    )
    serializer_class = TransferSerializer
    permission_classes = [role_permission(*TRANSFER_REQUESTERS)]
    filter_backends = [KeywordSearchFilter, NullsLastOrderingFilter]
    search_fields = ["reason", "fiscal_document_number", "origin__code", "destination__code"]
    ordering_fields = ["requested_at", "status", "sent_at", "received_at"]
    ordering = ["-requested_at"]

    def get_permissions(self):
        if self.action in ("pick", "send", "receive", "finish"):
            return [role_permission(*TRANSFER_HANDLERS)()]
        if self.action == "approve":
            return [role_permission(*SUPERVISORS)()]
        if self.action in ("files", "file_delete"):
            return [role_permission(*TRANSFER_REQUESTERS, *TRANSFER_HANDLERS)()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("status") == "open":
            queryset = queryset.filter(status__in=[*BEFORE_SENDING, TransferStatus.IN_TRANSIT])
        elif params.get("status") in TransferStatus.values:
            queryset = queryset.filter(status=params["status"])
        for param in ("origin", "destination"):
            if params.get(param, "").isdigit():
                queryset = queryset.filter(**{f"{param}_id": int(params[param])})
        if params.get("warehouse", "").isdigit():
            pk = int(params["warehouse"])
            queryset = queryset.filter(Q(origin_id=pk) | Q(destination_id=pk))
        return queryset

    def filter_queryset(self, queryset):
        match = re.fullmatch(
            r"\s*TRF-(\d{4})-(\d+)\s*", self.request.query_params.get("search", ""), re.I
        )
        if match:
            return queryset.filter(year=int(match[1]), sequence=int(match[2])).order_by("id")
        return super().filter_queryset(queryset)

    def _detail(self, transfer, code=200):
        transfer = self.get_queryset().get(pk=transfer.pk)
        context = self.get_serializer_context()
        data = self.get_serializer(transfer).data
        items = transfer.items.select_related(
            "asset__asset_model__manufacturer",
            "asset__asset_model__asset_class",
            "asset__customer",
            "asset__lot",
            "asset__current_location",
            "asset__current_container",
            "accessory_model__manufacturer",
            "container",
            "received_location",
        )
        data["items"] = TransferItemSerializer(items, many=True, context=context).data
        data["files"] = TransferFileSerializer(
            transfer.files.select_related("uploaded_by"), many=True, context=context
        ).data
        data["occurrences"] = OccurrenceSerializer(
            transfer.occurrences.select_related(
                "lot",
                "transfer",
                "asset",
                "asset_model__manufacturer",
                "responsible",
                "resolved_by",
            ).annotate(attachments_count=Count("attachments")),
            many=True,
            context=context,
        ).data
        data["problems"] = (
            [str(p) for p in transfers.problems(transfer)]
            if transfer.status in BEFORE_SENDING
            else []
        )
        return Response(data, status=code)

    def retrieve(self, request, *args, **kwargs):
        return self._detail(self.get_object())

    def _values(self, data, *, partial):
        serializer = self.get_serializer(data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def create(self, request, *args, **kwargs):
        values = self._values(request.data, partial=False)
        try:
            transfer = transfers.create(
                origin=values.get("origin"),
                destination=values.get("destination"),
                reason=values.get("reason", ""),
                user=request.user,
                transit_days=values.get("transit_days", 5),
                notes=values.get("notes", ""),
                keywords=values.get("keywords"),
            )
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer, 201)

    def update(self, request, *args, **kwargs):
        transfer = self.get_object()
        values = self._values(request.data, partial=True)
        allowed = {"reason", "transit_days", "notes", "keywords", "fiscal_document_number"}
        try:
            transfers.update_header(transfer, **{k: v for k, v in values.items() if k in allowed})
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    @action(detail=True, methods=["post"])
    def items(self, request, pk=None):
        transfer = self.get_object()
        try:
            if request.data.get("accessory_model"):
                model = AssetModel.objects.filter(pk=request.data["accessory_model"]).first()
                if model is None:
                    raise DomainError(_("Choose a valid model."), field="accessory_model")
                transfers.add_accessory(
                    transfer,
                    model,
                    int(request.data.get("quantity") or 0),
                    condition=request.data.get("condition") or AccessoryCondition.GOOD,
                )
            else:
                target = _read(
                    request.data.get("code"),
                    (Asset, Container),
                    "code",
                    _("Read the ID of an asset or a container."),
                )
                if isinstance(target, Container):
                    transfers.add_container(transfer, target)
                else:
                    transfers.add_asset(transfer, target)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    @action(detail=True, methods=["delete"], url_path=r"items/(?P<item_id>\d+)")
    def item(self, request, pk=None, item_id=None):
        transfer = self.get_object()
        item = transfer.items.filter(pk=item_id).first()
        if item is None:
            raise Http404
        try:
            transfers.remove_item(item)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        transfer = self.get_object()
        try:
            transfers.approve(transfer, user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    def _accessory_place(self, code):
        place = _read(
            code,
            (Container, Location),
            "code",
            _("Read the container or location of the accessories."),
        )
        return (
            place if isinstance(place, Container) else None,
            place if isinstance(place, Location) else None,
        )

    @action(detail=True, methods=["post"])
    def pick(self, request, pk=None):
        transfer = self.get_object()
        try:
            if request.data.get("item"):
                item = transfer.items.filter(pk=request.data["item"]).first()
                if item is None:
                    raise DomainError(_("Choose an item of the list."), field="item")
                container, location = self._accessory_place(request.data.get("code"))
                transfers.pick_accessory(
                    transfer,
                    item,
                    int(request.data.get("quantity") or 0),
                    user=request.user,
                    container=container,
                    location=location,
                )
            else:
                target = _read(
                    request.data.get("code"),
                    (Asset, Container),
                    "code",
                    _("Read the ID of an asset or a container."),
                )
                transfers.pick(transfer, target, user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        transfer = self.get_object()
        try:
            transfers.send(transfer, user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        transfer = self.get_object()
        try:
            if request.data.get("item"):
                item = transfer.items.filter(pk=request.data["item"]).first()
                if item is None:
                    raise DomainError(_("Choose an item of the list."), field="item")
                container, location = self._accessory_place(request.data.get("code"))
                transfers.receive_accessory(
                    transfer,
                    item,
                    int(request.data.get("quantity") or 0),
                    user=request.user,
                    container=container,
                    location=location,
                )
            else:
                location = _read(
                    request.data.get("location"),
                    Location,
                    "location",
                    _("Read the location first."),
                )
                target = _read(
                    request.data.get("code"),
                    (Asset, Container),
                    "code",
                    _("Read the ID of an asset or a container."),
                )
                transfers.receive(
                    transfer,
                    target,
                    location=location,
                    user=request.user,
                    damaged=bool(request.data.get("damaged")),
                    note=str(request.data.get("note") or ""),
                )
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        transfer = self.get_object()
        try:
            transfers.finish(transfer, user=request.user)
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        transfer = self.get_object()
        try:
            transfers.cancel(transfer, user=request.user, reason=request.data.get("reason", ""))
        except DomainError as exc:
            return domain_error(exc)
        return self._detail(transfer)

    @action(detail=True, methods=["get", "post"])
    def files(self, request, pk=None):
        transfer = self.get_object()
        if request.method == "POST":
            try:
                transfers.add_file(
                    transfer,
                    kind=request.data.get("kind", ""),
                    upload=_upload(request),
                    user=request.user,
                )
            except DomainError as exc:
                return domain_error(exc)
        return Response(
            TransferFileSerializer(
                transfer.files.select_related("uploaded_by"),
                many=True,
                context=self.get_serializer_context(),
            ).data
        )

    @action(detail=True, methods=["delete"], url_path=r"files/(?P<file_id>\d+)")
    def file_delete(self, request, pk=None, file_id=None):
        item = self.get_object().files.filter(pk=file_id).first()
        if item is None:
            raise Http404
        try:
            transfers.remove_file(item)
        except DomainError as exc:
            return domain_error(exc)
        return Response(status=204)

    @action(detail=True, methods=["get"], url_path=r"files/(?P<file_id>\d+)/file")
    def file_download(self, request, pk=None, file_id=None):
        item = self.get_object().files.filter(pk=file_id).first()
        if item is None:
            raise Http404
        return _file_response(item.file, item.name, item.content_type, inline=True)
