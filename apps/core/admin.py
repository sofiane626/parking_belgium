from django.contrib import admin

from .models import Commune


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ("niscode", "name_fr", "name_nl", "name_en")
    search_fields = ("niscode", "name_fr", "name_nl", "name_en")
    ordering = ("niscode",)
