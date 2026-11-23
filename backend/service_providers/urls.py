from rest_framework.routers import DefaultRouter

from .views import ServiceProviderViewSet

router = DefaultRouter()
router.register("", ServiceProviderViewSet, basename="service-provider")

urlpatterns = router.urls
