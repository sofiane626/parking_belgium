"""Development settings — DEBUG on, browsable DRF, permissive CORS."""
from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK, env

DEBUG = True

INTERNAL_IPS = ["127.0.0.1"]

# Make DRF browsable in dev for manual exploration.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

CORS_ALLOW_ALL_ORIGINS = True

# ----- EMAIL -----------------------------------------------------------------
# Si EMAIL_HOST est configuré dans .env → SMTP réel (Gmail / Mailtrap / etc.)
# Sinon → backend console (affiche dans le terminal runserver, pas d'envoi).
_email_host = env("EMAIL_HOST", default="")
if _email_host:
    # Backend SMTP qui force le CA bundle certifi — corrige les erreurs
    # CERTIFICATE_VERIFY_FAILED sur Python Microsoft Store / Windows.
    EMAIL_BACKEND = "apps.payments.email_backend.CertifiSMTPBackend"
    EMAIL_HOST = _email_host
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
    EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)
    # Antivirus / proxy intercepte SSL ? Mettre EMAIL_INSECURE_SKIP_VERIFY=True
    # dans .env pour bypass la validation du certificat. Dev uniquement.
    EMAIL_INSECURE_SKIP_VERIFY = env.bool("EMAIL_INSECURE_SKIP_VERIFY", default=False)
else:
    # Backend console UTF-8 (corrige l'UnicodeEncodeError sur Windows cp1252).
    EMAIL_BACKEND = "apps.payments.email_backend.EmailBackend"
