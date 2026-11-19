"""Autenticação por sessão para o frontend Vue."""

from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def _dados_usuario(usuario):
    return {
        "id": usuario.id,
        "username": usuario.username,
        "nome": usuario.get_full_name() or usuario.username,
        "is_staff": usuario.is_staff,
    }


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Garante que o navegador receba o cookie csrftoken."""
    return Response({"detail": "ok"})


@api_view(["POST"])
@permission_classes([AllowAny])
def entrar(request):
    usuario = authenticate(
        request,
        username=request.data.get("username", ""),
        password=request.data.get("password", ""),
    )
    if usuario is None:
        return Response(
            {"detail": "Usuário ou senha inválidos."}, status=status.HTTP_400_BAD_REQUEST
        )
    login(request, usuario)
    return Response(_dados_usuario(usuario))


@api_view(["POST"])
def sair(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def eu(request):
    return Response(_dados_usuario(request.user))
