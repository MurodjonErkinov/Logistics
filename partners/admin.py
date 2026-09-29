from django.contrib import admin

from .models import Company, CompanyMember


class CompanyMemberInline(admin.TabularInline):
    model = CompanyMember
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone_number", "created_by", "created_at")
    search_fields = ("name", "phone_number")
    inlines = (CompanyMemberInline,)


@admin.register(CompanyMember)
class CompanyMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "user", "role", "can_post_cargo")
    list_filter = ("role", "can_post_cargo")
