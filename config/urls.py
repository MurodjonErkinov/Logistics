from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("authentication.urls")),
    path("api/partners/", include("partners.urls")),
    path("api/cargo/", include("cargo.urls")),
]
