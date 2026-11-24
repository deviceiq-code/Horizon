from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccessoryBalanceViewSet,
    AppointmentViewSet,
    AssetViewSet,
    ContainerViewSet,
    ErasureToolViewSet,
    GradeLevelViewSet,
    InspectionViewSet,
    LabelRangeViewSet,
    LocationViewSet,
    LookupView,
    MovementViewSet,
    OccurrenceViewSet,
    PenaltyRateViewSet,
    ReceivingLotViewSet,
    WarehouseViewSet,
)

router = DefaultRouter()
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("locations", LocationViewSet, basename="location")
router.register("containers", ContainerViewSet, basename="container")
router.register("assets", AssetViewSet, basename="asset")
router.register("movements", MovementViewSet, basename="movement")
router.register("label-ranges", LabelRangeViewSet, basename="label-range")
router.register("appointments", AppointmentViewSet, basename="appointment")
router.register("lots", ReceivingLotViewSet, basename="lot")
router.register("occurrences", OccurrenceViewSet, basename="occurrence")
router.register("accessory-balances", AccessoryBalanceViewSet, basename="accessory-balance")
router.register("grade-levels", GradeLevelViewSet, basename="grade-level")
router.register("penalty-rates", PenaltyRateViewSet, basename="penalty-rate")
router.register("erasure-tools", ErasureToolViewSet, basename="erasure-tool")
router.register("inspections", InspectionViewSet, basename="inspection")

urlpatterns = [path("lookup/", LookupView.as_view(), name="inventory-lookup"), *router.urls]
