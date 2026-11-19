from rest_framework.routers import DefaultRouter

from .views import AveragePriceViewSet

router = DefaultRouter()
router.register("", AveragePriceViewSet, basename="average-price")

urlpatterns = router.urls
