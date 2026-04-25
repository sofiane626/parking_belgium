"""Development settings — DEBUG on, browsable DRF, permissive CORS."""
from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK

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

EMAIL_BACKEND = "apps.payments.email_backend.EmailBackend"
