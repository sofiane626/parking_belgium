from django.contrib import admin

from .models import PolygonRule


@admin.register(PolygonRule)
class PolygonRuleAdmin(admin.ModelAdmin):
    list_display = ("polygon", "permit_type", "action_type", "target_zone_code", "priority", "is_active")
    list_filter = ("permit_type", "action_type", "is_active", "commune")
    search_fields = ("polygon__zonecode", "target_zone_code", "description")
    raw_id_fields = ("polygon", "commune")
    readonly_fields = ("created_at", "updated_at", "created_by")
