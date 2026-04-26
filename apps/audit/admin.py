from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "severity", "action", "actor", "target_type", "target_id", "ip")
    list_filter = ("severity", "action", "target_type")
    search_fields = ("actor__username", "target_label", "ip")
    date_hierarchy = "created_at"
    readonly_fields = [
        "created_at", "actor", "actor_role", "action", "severity",
        "target_type", "target_id", "target_label", "payload", "ip",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # On laisse le delete superuser-only — utile pour purger en dev/test
        return request.user.is_superuser
