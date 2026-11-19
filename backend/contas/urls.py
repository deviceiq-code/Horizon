from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.csrf, name="auth-csrf"),
    path("login/", views.entrar, name="auth-login"),
    path("logout/", views.sair, name="auth-logout"),
    path("me/", views.eu, name="auth-me"),
]
