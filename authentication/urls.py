from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LoginView, RefreshView, LogoutView, ProfileView, RegisterView, UserViewSet,
    RegistrationCodeView, PasswordResetCodeView, PasswordResetView,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="users")

urlpatterns = [
    path("password-reset-code/", PasswordResetCodeView.as_view(), name="password-reset-code"),
    path("reset-password/", PasswordResetView.as_view(), name="reset-password"),
    path("registration-code/", RegistrationCodeView.as_view(), name="registration-code"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", ProfileView.as_view(), name="me"),
    path("", include(router.urls)),
]
