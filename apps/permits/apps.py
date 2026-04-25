from django.apps import AppConfig


class PermitsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.permits"
    label = "permits"
    verbose_name = "Cartes & demandes"

    def ready(self):
        # Wire cross-app signal subscribers (address_changed, vehicle_plate_changed).
        from . import handlers  # noqa: F401
