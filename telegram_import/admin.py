from django.contrib import admin

from .models import TelegramCursor, TelegramLoad, TelegramPost


class TelegramLoadInline(admin.TabularInline):
    model = TelegramLoad
    fields = ("position", "load", "status", "payload", "detail")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TelegramPost)
class TelegramPostAdmin(admin.ModelAdmin):
    list_display = ("chat_id", "message_id", "provider", "status", "posted_at", "expires_at")
    list_filter = ("status", "provider")
    search_fields = ("group_name", "text", "detail")
    readonly_fields = ("chat_id", "message_id", "group_name", "text", "provider", "posted_at", "expires_at", "retry_at", "imported_at", "updated_at")
    inlines = (TelegramLoadInline,)


@admin.register(TelegramCursor)
class TelegramCursorAdmin(admin.ModelAdmin):
    list_display = ("chat_id", "last_message_id")
