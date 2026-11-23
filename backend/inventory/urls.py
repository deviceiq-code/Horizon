from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AssetViewSet,
    ContainerViewSet,
    LabelRangeViewSet,
    LocationViewSet,
    LookupView,
    MovementViewSet,
    WarehouseViewSet,
)

router = DefaultRouter()
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("locations", LocationViewSet, basename="location")
router.register("containers", ContainerViewSet, basename="container")
router.register("assets", AssetViewSet, basename="asset")
router.register("movements", MovementViewSet, basename="movement")
router.register("label-ranges", LabelRangeViewSet, basename="label-range")

urlpatterns = [path("lookup/", LookupView.as_view(), name="inventory-lookup"), *router.urls]
