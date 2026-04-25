from django.contrib import admin

from .models import PlateChangeRequest, Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate", "owner", "vehicle_type", "brand", "model", "updated_at")
    list_filter = ("vehicle_type",)
    search_fields = ("plate", "owner__username", "brand", "model")
    autocomplete_fields = ("owner",)


@admin.register(PlateChangeRequest)
class PlateChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "new_plate", "status", "submitted_at", "decided_by")
    list_filter = ("status",)
    search_fields = ("vehicle__plate", "new_plate", "vehicle__owner__username")
    readonly_fields = ("submitted_at",)
