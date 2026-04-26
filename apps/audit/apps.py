from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    label = "audit"
    verbose_name = "Audit"

    def ready(self) -> None:
        # Branche les signaux passifs (PolygonRule, CommunePermitPolicy, PermitConfig).
        # Les services métier loggent directement, pas besoin de signaux pour eux.
        from . import signals  # noqa: F401
