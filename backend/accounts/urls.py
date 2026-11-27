from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.csrf, name="auth-csrf"),
    path("environments/", views.environments_view, name="auth-environments"),
    path("login/", views.login_view, name="auth-login"),
    path("logout/", views.logout_view, name="auth-logout"),
    path("me/", views.me, name="auth-me"),
    path("preferences/", views.preferences, name="auth-preferences"),
    path("preferences/test-searxng/", views.test_searxng, name="auth-test-searxng"),
]
