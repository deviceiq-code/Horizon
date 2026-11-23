from django.db.models import Count, Q
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
from users.models import INVENTORY_SUPERVISOR

from . import services
from .models import (
    Asset,
    Container,
    ContainerKind,
    LabelRange,
    Location,
    MovementEvent,
    Ownership,
    Warehouse,
)
from .permissions import (
    LABELERS,
    LOCATION_KEEPERS,
    MOVERS,
    IsAdministratorToWrite,
    has_role,
    role_permission,
)
from .serializers import (
    AssetEntrySerializer,
    AssetSerializer,
    ContainerSerializer,
    LabelRangeSerializer,
    LocationSerializer,
    MovementEventSerializer,
    MovementSerializer,
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
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Assets in stock. Never deleted (their history stays).

    List supports ?search= (Horizon ID, serial, model, manufacturer), ?status=, ?warehouse=,
    ?location=, ?container=, ?asset_model=, ?asset_class=, ?name= (Horizon ID, serial or model
    contains), ?ordering=, pagination. GET <id>/ includes `events` (its whole history).
    POST (administrators): manual entry at a dock until triage exists (Phase 2).
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
        if self.action == "create":
            return [IsAdministratorToWrite()]
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

    def create(self, request, *args, **kwargs):
        entry = AssetEntrySerializer(data=request.data)
        entry.is_valid(raise_exception=True)
        data = entry.validated_data
        model = (
            AssetModel.objects.filter(pk=data["asset_model"]).select_related("asset_class").first()
        )
        if model is None:
            return Response({"asset_model": [_("Choose a valid model.")]}, status=400)
        try:
            place = services.resolve_code(data["location"], field="location")
            container = place if isinstance(place, Container) else None
            if not isinstance(place, (Location, Container)):
                raise DomainError(_("Read a location or a container."), field="location")
            asset = services.register_entry(
                asset_model=model,
                location=container.current_location if container else place,
                container=container,
                user=request.user,
                serial=data["serial"],
                no_serial_reason=data["no_serial_reason"],
                other_ids=data["other_ids"],
                horizon_id=data["horizon_id"],
                reason=data["reason"],
            )
        except DomainError as exc:
            return domain_error(exc)
        return Response(self.get_serializer(asset).data, status=status.HTTP_201_CREATED)

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
