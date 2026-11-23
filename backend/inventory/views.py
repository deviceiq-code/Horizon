import re

from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from catalogs.models import AssetModel
from catalogs.views import RefuseDeletingWhenInUse
from config.filters import NullsLastOrderingFilter
from config.keywords import KeywordSearchFilter
from config.parties import column_filters
from pricing.documents import opens_inline
from users.models import INVENTORY_SUPERVISOR

from . import receiving, services
from .expected import model_key, parse_pasted
from .models import (
    AccessoryBalance,
    AccessoryCondition,
    Appointment,
    AppointmentKind,
    AppointmentStatus,
    Asset,
    AttachmentKind,
    Container,
    ContainerKind,
    ExpectedItem,
    LabelRange,
    Location,
    LotStatus,
    MovementEvent,
    Occurrence,
    OccurrenceKind,
    OccurrenceStatus,
    Ownership,
    ReceivingLot,
    Warehouse,
)
from .permissions import (
    EXPECTED_READERS,
    LABELERS,
    LOCATION_KEEPERS,
    MOVERS,
    RECEIVERS,
    SCHEDULERS,
    has_role,
    role_permission,
)
from .serializers import (
    AccessoryBalanceSerializer,
    AppointmentSerializer,
    AssetSerializer,
    ContainerSerializer,
    ExpectedItemSerializer,
    LabelRangeSerializer,
    LocationSerializer,
    LotAttachmentSerializer,
    LotOpenSerializer,
    MovementEventSerializer,
    MovementSerializer,
    OccurrenceSerializer,
    ReceivingLotSerializer,
    WarehouseSerializer,
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
        "lot", "asset", "asset_model__manufacturer", "responsible", "resolved_by"
    ).annotate(attachments_count=Count("attachments"))
    serializer_class = OccurrenceSerializer
    permission_classes = [role_permission(*RECEIVERS)]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("lot", "").isdigit():
            queryset = queryset.filter(lot_id=int(params["lot"]))
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
