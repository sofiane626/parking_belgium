from django.contrib import admin

from .models import CommunePermitPolicy, Permit, PermitConfig, PermitZone, VisitorCode


class PermitZoneInline(admin.TabularInline):
    model = PermitZone
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Permit)
class PermitAdmin(admin.ModelAdmin):
    list_display = ("id", "citizen", "vehicle", "permit_type", "status", "valid_until")
    list_filter = ("permit_type", "status")
    search_fields = ("citizen__username", "vehicle__plate", "decision_notes")
    raw_id_fields = ("citizen", "vehicle", "decided_by", "source_polygon", "company", "target_commune")
    readonly_fields = (
        "submitted_at", "decided_at", "awaiting_payment_at", "paid_at",
        "activated_at", "suspended_at", "expired_at", "cancelled_at",
        "attribution_snapshot",
    )
    inlines = [PermitZoneInline]


@admin.register(PermitZone)
class PermitZoneAdmin(admin.ModelAdmin):
    list_display = ("permit", "zone_code", "is_main", "source")
    list_filter = ("source", "is_main")
    search_fields = ("permit__citizen__username", "zone_code")


@admin.register(VisitorCode)
class VisitorCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "permit", "plate", "valid_from", "valid_until", "status")
    list_filter = ("status",)
    search_fields = ("code", "plate", "permit__citizen__username")
    readonly_fields = ("created_at", "cancelled_at")


@admin.register(PermitConfig)
class PermitConfigAdmin(admin.ModelAdmin):
    list_display = ("__str__", "updated_at", "updated_by")


@admin.register(CommunePermitPolicy)
class CommunePermitPolicyAdmin(admin.ModelAdmin):
    list_display = ("commune", "permit_type", "is_enabled", "price_strategy", "validity_days", "effective_from", "effective_until")
    list_filter = ("permit_type", "is_enabled", "price_strategy", "commune")
    search_fields = ("commune__name_fr", "notes")
