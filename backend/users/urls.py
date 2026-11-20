from rest_framework.routers import DefaultRouter

from .views import AccountManagerViewSet, RoleViewSet, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("account-managers", AccountManagerViewSet, basename="account-manager")

urlpatterns = router.urls
