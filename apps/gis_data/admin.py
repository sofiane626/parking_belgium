from django.contrib.gis import admin as gisadmin

from .models import GISPolygon, GISSourceVersion


@gisadmin.register(GISSourceVersion)
class GISSourceVersionAdmin(gisadmin.ModelAdmin):
    list_display = ("name", "polygon_count", "is_active", "imported_at")
    list_filter = ("is_active",)
    search_fields = ("name", "source_filename")


@gisadmin.register(GISPolygon)
class GISPolygonAdmin(gisadmin.GISModelAdmin):
    list_display = ("zonecode", "niscode", "commune", "version", "type")
    list_filter = ("version", "commune")
    search_fields = ("zonecode", "niscode", "name_fr", "name_nl", "name_en", "layer")
    raw_id_fields = ("version", "commune")
