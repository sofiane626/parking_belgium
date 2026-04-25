from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "permit", "citizen", "amount_cents", "method", "status", "initiated_at", "confirmed_at")
    list_filter = ("status", "method")
    search_fields = ("reference", "citizen__username", "citizen__email", "permit__id", "external_transaction_id")
    raw_id_fields = ("permit", "citizen")
    readonly_fields = (
        "reference", "initiated_at", "confirmed_at", "failed_at",
        "cancelled_at", "refunded_at", "initiated_from_ip", "confirmed_from_ip",
    )
    ordering = ("-initiated_at",)
