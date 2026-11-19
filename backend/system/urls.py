from django.urls import path

from . import views

urlpatterns = [
    path("settings/", views.system_settings, name="system-settings"),
    path("settings/test-searxng/", views.test_searxng, name="system-test-searxng"),
]
