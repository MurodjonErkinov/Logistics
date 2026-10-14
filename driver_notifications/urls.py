from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, PreferenceView, TelegramLinkView, TicketViewSet, VehicleViewSet

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="driver-vehicle")
router.register("tickets", TicketViewSet, basename="driver-ticket")
router.register("notifications", NotificationViewSet, basename="driver-notification")
urlpatterns = [path("", include(router.urls)), path("preferences/", PreferenceView.as_view()), path("telegram-link/", TelegramLinkView.as_view())]
