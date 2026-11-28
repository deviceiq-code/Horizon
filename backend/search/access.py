"""A module's list as the signed-in user may see it: its own ViewSet (permissions and queryset)
called for the request — shared by the centralized search and the Home's journal."""

import copy

from django.http import QueryDict
from rest_framework.exceptions import APIException
from rest_framework.request import Request


def module_view(view_class: type, request, params: dict | None = None):
    """The module's ViewSet ready to list for this user (with `params` as its query string), or
    None when the user may not open it."""
    http = copy.copy(request._request)
    http.GET = QueryDict(mutable=True)
    for key, value in (params or {}).items():
        http.GET[key] = value
    sub = Request(http, parsers=request.parsers, authenticators=request.authenticators)
    sub.user = request.user
    sub._auth = request.auth
    view = view_class()
    view.request = sub
    view.args, view.kwargs = (), {}
    view.action = "list"
    view.format_kwarg = None
    view.headers = {}
    try:
        view.check_permissions(sub)
    except APIException:
        return None
    return view
