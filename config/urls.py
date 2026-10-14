from django.contrib import admin
from django.urls import include, path
from .health import health

urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),
    path("api/auth/", include("authentication.urls")),
    path("api/partners/", include("partners.urls")),
    path("api/driver/", include("driver_notifications.urls")),
    path("api/cargo/", include("cargo.urls")),
]
