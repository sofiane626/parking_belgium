from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import AdminLoginForm
from .models import User

# La connexion à /admin/ subit le même verrouillage anti brute-force que le site.
admin.site.login_form = AdminLoginForm


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Rôle", {"fields": ("role",)}),)
