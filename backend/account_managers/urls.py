from rest_framework.routers import DefaultRouter

from .views import AccountManagerViewSet

router = DefaultRouter()
router.register("", AccountManagerViewSet, basename="account-manager")

urlpatterns = router.urls
