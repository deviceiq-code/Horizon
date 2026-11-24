"""Horizon settings. Sensitive values come from the .env file at the repository root."""

from pathlib import Path

import environ

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

DATABASES = {"default": env.db("DATABASE_URL")}

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
MEDIA_ROOT = env.path("MEDIA_ROOT", default=str(BASE_DIR / "media"))
MEDIA_URL = "media/"
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
