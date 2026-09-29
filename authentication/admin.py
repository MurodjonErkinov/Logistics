from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Logistics", {"fields": ("phone_number", "role")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Logistics", {"fields": ("phone_number", "role")}),)
    list_display = DjangoUserAdmin.list_display + ("phone_number", "role")
