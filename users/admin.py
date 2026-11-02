from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "email_verified", "subscription_level", "is_staff")
    list_filter = BaseUserAdmin.list_filter + ("email_verified", "subscription_level")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Демо-поля урока", {"fields": ("email_verified", "subscription_level")}),
    )
