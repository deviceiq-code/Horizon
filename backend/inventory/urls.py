from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccessoryBalanceViewSet,
    AgingLimitViewSet,
    AlertViewSet,
    AppointmentViewSet,
    AssetViewSet,
    BlockFollowUpViewSet,
    ChargeViewSet,
    ContainerViewSet,
    DeadlineCheckView,
    DeadlineSettingViewSet,
    DisposalViewSet,
    DisputeViewSet,
    ErasureToolViewSet,
    GradeLevelViewSet,
    HolidayViewSet,
    InspectionViewSet,
    LabelRangeViewSet,
    LocationViewSet,
    LookupView,
    MovementViewSet,
    OccurrenceViewSet,
    PenaltyRateViewSet,
    ReceivingLotViewSet,
    StockAssetViewSet,
    StockView,
    TransferViewSet,
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
router.register("deadline-settings", DeadlineSettingViewSet, basename="deadline-setting")
router.register("aging-limits", AgingLimitViewSet, basename="aging-limit")
router.register("holidays", HolidayViewSet, basename="holiday")
router.register("blocks", BlockFollowUpViewSet, basename="block")
router.register("disputes", DisputeViewSet, basename="dispute")
router.register("charges", ChargeViewSet, basename="charge")
router.register("alerts", AlertViewSet, basename="alert")
router.register("stock/assets", StockAssetViewSet, basename="stock-asset")
router.register("disposals", DisposalViewSet, basename="disposal")
router.register("transfers", TransferViewSet, basename="transfer")

urlpatterns = [
    path("lookup/", LookupView.as_view(), name="inventory-lookup"),
    path("deadline-check/", DeadlineCheckView.as_view(), name="inventory-deadline-check"),
    path("stock/", StockView.as_view(), name="inventory-stock"),
    *router.urls,
]
