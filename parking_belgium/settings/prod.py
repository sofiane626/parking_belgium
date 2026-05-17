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

# ----- Email SMTP -----------------------------------------------------------
# Même logique que dev.py : si EMAIL_HOST est fourni → SMTP réel, sinon backend
# console (utile pour les premiers déploiements avant que le secret SMTP ne
# soit configuré). On garde le CertifiSMTPBackend pour rester homogène avec
# le code applicatif (forçage certifi inoffensif sous Linux).
_email_host = env("EMAIL_HOST", default="")
if _email_host:
    EMAIL_BACKEND = "apps.payments.email_backend.CertifiSMTPBackend"
    EMAIL_HOST = _email_host
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
    EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)
    # En prod, jamais de skip de la vérif SSL (contournement antivirus local
    # uniquement). On force la valeur à False pour neutraliser un éventuel
    # oubli dans les variables d'environnement.
    EMAIL_INSECURE_SKIP_VERIFY = False
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
