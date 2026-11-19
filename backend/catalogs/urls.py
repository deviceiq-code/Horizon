from rest_framework.routers import DefaultRouter

from .views import VerticalViewSet

router = DefaultRouter()
router.register("verticals", VerticalViewSet, basename="vertical")

urlpatterns = router.urls
