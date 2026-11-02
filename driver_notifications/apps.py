from django.apps import AppConfig


class DriverNotificationsConfig(AppConfig):
    name = "driver_notifications"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401
