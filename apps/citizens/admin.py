from django.contrib import admin

from .models import Address, AddressChangeRequest, CitizenProfile


class AddressInline(admin.StackedInline):
    model = Address
    extra = 0
    fields = ("street", "number", "box", "postal_code", "commune", "country", "location")


@admin.register(CitizenProfile)
class CitizenProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "date_of_birth", "updated_at")
    search_fields = ("user__username", "user__email", "national_number", "phone")
    inlines = [AddressInline]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("profile", "street", "number", "postal_code", "commune")
    list_filter = ("commune",)
    search_fields = ("street", "postal_code", "profile__user__username")


@admin.register(AddressChangeRequest)
class AddressChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("profile", "street", "postal_code", "commune", "status", "submitted_at", "decided_by")
    list_filter = ("status", "commune")
    search_fields = ("profile__user__username", "street", "postal_code")
    readonly_fields = ("submitted_at",)
