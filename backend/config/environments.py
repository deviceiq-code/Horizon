"""Environments: Live and Development (Test) — the same system over different databases.

Each environment is a whole database of its own (users, sessions, preferences and data) and a
folder of uploaded files of its own. The process serves its own environment (`HORIZON_ENVIRONMENT`
in `.env`, default "live"; management commands run there) and, per request, the one chosen on
the login page (the `horizon_environment` cookie).

A request in another environment swaps this thread's "default" database connection for that
environment's, so everything that uses the default — sessions, `transaction.atomic()`,
`select_for_update`, raw cursors — goes to the same database, with no `using=` anywhere.
"""

import contextvars
import os
from contextlib import contextmanager

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import DEFAULT_DB_ALIAS, connections
from django.utils.translation import gettext_lazy as _

LIVE = "live"
DEVELOPMENT = "development"
# In the order offered on the login page
KNOWN = (LIVE, DEVELOPMENT)

# Their names (the frontend has its own: environments.<key>)
NAMES = {LIVE: _("Live"), DEVELOPMENT: _("Development (Test)")}

COOKIE_NAME = "horizon_environment"

_current: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "horizon_environment", default=None
)


def label(name: str) -> str:
    return str(NAMES.get(name, name))


def process_environment() -> str:
    """The environment of this process (its "default" database)."""
    return settings.HORIZON_ENVIRONMENT


def available() -> list[str]:
    """The environments configured in `.env`, in KNOWN's order."""
    return [name for name in KNOWN if name in settings.HORIZON_DATABASES]


def current() -> str:
    """The environment being served now (the request's, else the process's)."""
    return _current.get() or process_environment()


def chosen(value: str | None) -> str:
    """The environment a request asks for (its cookie), the process's when unknown."""
    return value if value in available() else process_environment()


def alias(name: str) -> str:
    """The database alias of an environment: the process's own is "default"."""
    return DEFAULT_DB_ALIAS if name == process_environment() else name


def media_root(name: str | None = None) -> str:
    """Where an environment's uploaded files live (the process's: MEDIA_ROOT)."""
    name = name or current()
    if name == process_environment():
        return str(settings.MEDIA_ROOT)
    return str(settings.HORIZON_MEDIA_ROOTS[name])


def _clear_caches() -> None:
    # Content types are cached per alias ("default" in both environments)
    from django.contrib.contenttypes.models import ContentType

    ContentType.objects.clear_cache()


# While another environment is served: this process's own "default" connection (to come back
# to it, e.g. Live's users read from a request in Development)
_own_connection: contextvars.ContextVar = contextvars.ContextVar(
    "horizon_own_connection", default=None
)


def connection_of(name: str):
    """An environment's own connection, whatever "default" serves now (e.g. Live's from a
    request in Development)."""
    if alias(name) == DEFAULT_DB_ALIAS:
        return _own_connection.get() or connections[DEFAULT_DB_ALIAS]
    return connections[name]


@contextmanager
def activate(name: str):
    """Serve `name` within the block: its database as "default", its files as media. Nests: a
    request in Development may activate Live for a moment (users live there)."""
    if name not in available():
        raise ValueError(f"Unknown environment: {name}")
    token = _current.set(name)
    showing = connections[DEFAULT_DB_ALIAS]
    own = _own_connection.get()
    wanted = own if alias(name) == DEFAULT_DB_ALIAS else connections[name]
    if wanted is None or wanted is showing:
        try:
            yield
        finally:
            _current.reset(token)
        return
    own_token = _own_connection.set(own or showing)
    connections[DEFAULT_DB_ALIAS] = wanted
    _clear_caches()
    try:
        yield
    finally:
        connections[DEFAULT_DB_ALIAS] = showing
        _own_connection.reset(own_token)
        _current.reset(token)
        _clear_caches()


class EnvironmentMiddleware:
    """Serve each request in the environment its cookie chose. Must come before sessions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        name = chosen(request.COOKIES.get(COOKIE_NAME))
        request.environment = name
        with activate(name):
            return self.get_response(request)


class EnvironmentStorage(FileSystemStorage):
    """Uploaded files in the current environment's folder."""

    @property
    def base_location(self):
        return media_root()

    @property
    def location(self):
        return os.path.abspath(self.base_location)
