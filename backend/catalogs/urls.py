from rest_framework.routers import DefaultRouter

from .views import AssetClassViewSet, ManufacturerViewSet, SubVerticalViewSet, VerticalViewSet

router = DefaultRouter()
router.register("verticals", VerticalViewSet, basename="vertical")
router.register("sub-verticals", SubVerticalViewSet, basename="sub-vertical")
router.register("manufacturers", ManufacturerViewSet, basename="manufacturer")
router.register("asset-classes", AssetClassViewSet, basename="asset-class")

urlpatterns = router.urls
