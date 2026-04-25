from django.apps import AppConfig


class GisDataConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.gis_data"
    label = "gis_data"
    verbose_name = "Données GIS"
