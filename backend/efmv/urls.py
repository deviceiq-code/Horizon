from rest_framework.routers import DefaultRouter

from .views import EfmvAnalysisViewSet

router = DefaultRouter()
router.register("", EfmvAnalysisViewSet, basename="efmv-analysis")

urlpatterns = router.urls
