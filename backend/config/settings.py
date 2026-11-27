"""Horizon settings. Sensitive values come from the .env file at the repository root."""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:5173"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # ArrayField (e.g. sub-vertical allowed terms)
    # Third party
    "rest_framework",
    # Project
    "accounts",
    "assets",
    "partners",
    "account_managers",
    "customers",
    "catalogs",
    "pricing",
    "system",
    "users",
    "efmv",
    "service_providers",
    "inventory",
]

MIDDLEWARE = [
    # Live or Development: the database of everything below, sessions included
    "config.environments.EnvironmentMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Anonymous visitors: language from the Accept-Language header sent by the frontend
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Logged-in users: the language saved in their preferences wins
    "accounts.middleware.UserLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Environments (config/environments.py): Live and, when configured, Development (Test) — each a
# database of its own, chosen on the login page. "default" is this process's own environment
# (HORIZON_ENVIRONMENT; management commands run there); the others get an alias of their name.
HORIZON_DATABASES = {"live": env.db("DATABASE_URL")}
if env("DATABASE_URL_DEVELOPMENT", default=""):
    HORIZON_DATABASES["development"] = env.db("DATABASE_URL_DEVELOPMENT")
HORIZON_ENVIRONMENT = env("HORIZON_ENVIRONMENT", default="live")
if HORIZON_ENVIRONMENT not in HORIZON_DATABASES:
    raise ImproperlyConfigured(
        f"HORIZON_ENVIRONMENT={HORIZON_ENVIRONMENT!r} has no database "
        "(DATABASE_URL for live, DATABASE_URL_DEVELOPMENT for development)."
    )
DATABASES = {"default": HORIZON_DATABASES[HORIZON_ENVIRONMENT]}
for _name, _database in HORIZON_DATABASES.items():
    if _name != HORIZON_ENVIRONMENT:
        # In tests the other environments use the test database
        DATABASES[_name] = {**_database, "TEST": {"MIRROR": "default"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
# Supported languages. When adding one, also create:
#   backend/locale/<locale>/LC_MESSAGES/django.po  and  frontend/src/i18n/locales/<code>.ts
LANGUAGES = [
    ("en", "English"),
    ("pt-br", "Português (Brasil)"),
    ("es", "Español"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded files (e.g. average price documents). Not served publicly: downloads go through the
# API, which requires login.
# One folder per environment (config/environments.py); MEDIA_ROOT is this process's own.
HORIZON_MEDIA_ROOTS = {
    "live": env.path("MEDIA_ROOT", default=str(BASE_DIR / "media")),
    "development": env.path("MEDIA_ROOT_DEVELOPMENT", default=str(BASE_DIR / "media-development")),
}
MEDIA_ROOT = HORIZON_MEDIA_ROOTS[HORIZON_ENVIRONMENT]
MEDIA_URL = "media/"
STORAGES = {
    "default": {"BACKEND": "config.environments.EnvironmentStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PRICE_DOCUMENT_MAX_MB = env.int("PRICE_DOCUMENT_MAX_MB", default=25)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    # Decimals travel as strings so JavaScript does not lose precision
    "COERCE_DECIMAL_TO_STRING": True,
}

SESSION_COOKIE_AGE = 60 * 60 * 10  # 10 hours
