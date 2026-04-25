from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "vat_number", "owner", "commune", "updated_at")
    search_fields = ("name", "vat_number", "owner__username")
    list_filter = ("commune",)
    autocomplete_fields = ("owner",)
