"""WSGI entry point for parking_belgium."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "parking_belgium.settings.dev")

application = get_wsgi_application()
