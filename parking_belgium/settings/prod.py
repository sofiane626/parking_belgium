"""Production settings — hardened defaults. Override via env."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# ----- Hosts & CSRF ---------------------------------------------------------
# DJANGO_ALLOWED_HOSTS et CSRF_TRUSTED_ORIGINS sont des CSV. On accepte aussi
# bien le domaine Railway généré (*.up.railway.app) qu'un éventuel domaine
# custom — il suffit d'ajouter la valeur dans la variable d'env.
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=[".up.railway.app", ".railway.app"],
)
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=["https://*.up.railway.app", "https://*.railway.app"],
)

# ----- HTTPS / proxy --------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# ----- Fichiers statiques & médias -----------------------------------------
# Whitenoise sert /static/ en prod (déjà branché dans MIDDLEWARE base.py).
# MEDIA_ROOT pointe vers un volume Railway monté sur /data pour persister les
# uploads (justificatifs, passeports) entre redéploiements.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_ROOT = env("DJANGO_MEDIA_ROOT", default="/data/media")

# Django-tailwind cherche un binaire npm — en prod le build se fait en phase
# build (nixpacks), donc cette commande ne devrait jamais tourner, mais on
# pointe vers le `npm` du PATH par sécurité (Windows path absent sous Linux).
NPM_BIN_PATH = env("NPM_BIN_PATH", default="npm")

# ----- Email -----------------------------------------------------------
# Railway bloque tout trafic sortant ressemblant à du SMTP (ports 25, 465,
# 587, 2525 — testé). Cf. https://docs.railway.app/reference/outbound-emails
# On passe donc par l'API HTTP de Brevo via django-anymail (HTTPS:443, non
# bloqué). Le compte Brevo et les templates Django existants sont conservés
# tels quels — seul le « tuyau » d'envoi change. Si BREVO_API_KEY n'est pas
# fourni, on retombe sur le backend console (mails dans les logs Railway).
_brevo_api_key = env("BREVO_API_KEY", default="")
if _brevo_api_key:
    INSTALLED_APPS = INSTALLED_APPS + ["anymail"]  # noqa: F405
    EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
    ANYMAIL = {"BREVO_API_KEY": _brevo_api_key}
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ----- Audit -----------------------------------------------------------------
# Clé HMAC utilisée par apps.audit.services.hash_plate pour anonymiser les
# plaques dans les logs d'audit tout en restant corrélable.
PLATE_HMAC_KEY = env("PLATE_HMAC_KEY")

# ----- Logging vers stdout (Railway agrège) --------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
