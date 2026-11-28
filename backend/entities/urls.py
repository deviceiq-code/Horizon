from rest_framework.routers import DefaultRouter

from .views import BusinessEntityViewSet

router = DefaultRouter()
router.register("", BusinessEntityViewSet, basename="business-entity")

urlpatterns = router.urls
