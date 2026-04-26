"""
Base settings shared by dev and prod.

Reads environment from a `.env` file at the repo root via django-environ.
Per-environment settings inherit from this module and override what they need.
"""
import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# GeoDjango on Windows: point to the GDAL/GEOS DLLs shipped by the PostGIS bundle.
# Both vars are optional (POSIX systems usually find them via the loader).
GDAL_LIBRARY_PATH = env("GDAL_LIBRARY_PATH", default=None)
GEOS_LIBRARY_PATH = env("GEOS_LIBRARY_PATH", default=None)
# PROJ database path — required by GDAL for SRS lookups (e.g. EPSG:31370 → 4326
# reprojection). The PostGIS Windows bundle ships proj.db inside its share dir.
# PROJ 8+ uses PROJ_DATA; older PROJ used PROJ_LIB. We set both for safety.
_proj_lib = env("PROJ_LIB", default=None)
if _proj_lib:
    os.environ["PROJ_LIB"] = _proj_lib
    os.environ["PROJ_DATA"] = _proj_lib

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_extensions",
    "tailwind",
    "theme",
]

TAILWIND_APP_NAME = "theme"
# Explicit path keeps `manage.py tailwind ...` working regardless of the venv's PATH.
NPM_BIN_PATH = r"C:\Program Files\nodejs\npm.cmd"

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.citizens",
    "apps.vehicles",
    "apps.companies",
    "apps.permits",
    "apps.gis_data",
    "apps.rules",
    "apps.payments",
    "apps.audit",
    "apps.api",
    "apps.dashboard",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "parking_belgium.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "parking_belgium.wsgi.application"
ASGI_APPLICATION = "parking_belgium.asgi.application"

DATABASES = {
    "default": env.db_url("DATABASE_URL"),
}
# Force the GeoDjango backend even if django-environ resolved a plain postgres URL.
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
# Test DB inherits from a template that already has the postgis extension, so
# the project role doesn't need CREATE EXTENSION (i.e. SUPERUSER) privileges.
DATABASES["default"]["TEST"] = {"TEMPLATE": "template_postgis"}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:post_login_redirect"
LOGOUT_REDIRECT_URL = "core:home"

# i18n — FR primary, NL and EN supported.
LANGUAGE_CODE = "fr"
LANGUAGES = [
    ("fr", "Français"),
    ("nl", "Nederlands"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Brussels"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Permit pricing in cents (overridable per-deployment in dev/prod settings or
# via a future commune-level configuration table).
PERMIT_PRICES_CENTS = {
    "resident": 1000,        # 10 € / year — placeholder, varies by commune
    "visitor": 0,            # codes generated for free by default
    "professional": 5000,    # 50 € / year — placeholder
}
PERMIT_DEFAULT_VALIDITY_DAYS = 365

# Visitor permit configuration (spec: 100 codes / year, valid 1 Jan → 1 Dec).
VISITOR_CODES_PER_YEAR = 100
VISITOR_CODE_DEFAULT_HOURS = 4
VISITOR_PERMIT_PERIOD = (1, 1, 12, 1)  # (start_month, start_day, end_month, end_day)

# Email — DEFAULT_FROM_EMAIL is used as the sender for transactional notifications
# (paiement validé, remboursement…). Override per environment.
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="Parking.Belgium <no-reply@parking.belgium.local>")

# Stripe (test mode) — laisser vides pour désactiver l'option carte bancaire et
# ne garder que la simulation locale. Récupérer les clés sur
# https://dashboard.stripe.com/test/apikeys (compte gratuit). Le webhook secret
# vient de la CLI ``stripe listen --forward-to localhost:8000/me/payments/stripe/webhook/``.
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_CURRENCY = env("STRIPE_CURRENCY", default="eur")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "60/min",
        "anon": "10/min",
        "check_right": "120/min",
    },
}
