from django.contrib import admin

from .models import Load


@admin.register(Load)
class LoadAdmin(admin.ModelAdmin):
    list_display = ("id", "origin", "destination", "cargo_name", "weight_tons", "status", "posted_by", "company")
    list_filter = ("status", "currency", "is_price_negotiable")
    search_fields = ("origin", "destination", "cargo_name", "contact_phone")
