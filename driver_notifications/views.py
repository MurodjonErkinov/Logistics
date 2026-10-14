import os
from datetime import timedelta
from types import SimpleNamespace

from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MatchState, Notification, Preference, TelegramAccount, Ticket, Vehicle
from .serializers import NotificationSerializer, PreferenceSerializer, TicketSerializer, VehicleSerializer
from .service import new_link, notify, scan_ticket


class IsDriver(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and request.user.role == "driver")


class OwnedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsDriver]

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class VehicleViewSet(OwnedViewSet):
    queryset = Vehicle.objects.order_by("id")
    serializer_class = VehicleSerializer

    def perform_update(self, serializer):
        capacity = serializer.validated_data.get("capacity_tons", serializer.instance.capacity_tons)
        if Ticket.objects.filter(vehicle=serializer.instance, status__in=["active", "paused"], available_tons__gt=capacity).exists():
            raise serializers.ValidationError("Update ticket capacity before reducing the vehicle capacity.")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({"detail": "Delete linked tickets before deleting this vehicle."}, status=409)


class TicketViewSet(OwnedViewSet):
    queryset = Ticket.objects.select_related("vehicle")
    serializer_class = TicketSerializer

    def perform_create(self, serializer):
        if Ticket.objects.filter(owner=self.request.user, status__in=["active", "paused"]).count() >= 20:
            raise serializers.ValidationError("At most 20 active or paused tickets.")
        ticket = serializer.save(owner=self.request.user)
        notify(ticket, "ticket_created", f"ticket:{ticket.pk}")
        scan_ticket(ticket.pk)

    def perform_update(self, serializer):
        ticket = serializer.save()
        scan_ticket(ticket.pk)

    @action(detail=True, methods=["post"], url_path="return-trip")
    def return_trip(self, request, pk=None):
        ticket = self.get_object()
        data = dict(TicketSerializer(ticket).data)
        for field in ("id", "vehicle_name", "created_at", "updated_at"):
            data.pop(field, None)
        if ticket.route_mode == "anywhere":
            raise serializers.ValidationError("Select a destination before creating a return trip.")
        data.update(title=f"↩ {ticket.title}"[:120], origins=ticket.destinations, destinations=ticket.origins,
                    waypoints=list(reversed(ticket.waypoints)), current_location={}, status="paused",
                    ready_at=request.data.get("ready_at", timezone.now()),
                    expires_at=request.data.get("expires_at", timezone.now() + timedelta(days=7)))
        data.pop("current_location")
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NotificationPagination(PageNumberPagination):
    page_size = 30


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsDriver]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notification.objects.filter(owner=self.request.user).select_related("ticket", "load", "load__telegram_entry")

    @action(detail=False, methods=["get"])
    def unread(self, request):
        return Response({"count": self.get_queryset().filter(read_at=None).count()})

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        self.get_queryset().filter(read_at=None).update(read_at=timezone.now())
        return Response({"ok": True})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        note = self.get_object()
        note.read_at = timezone.now()
        note.save(update_fields=["read_at"])
        return Response(self.get_serializer(note).data)

    @action(detail=True, methods=["post"])
    def dismiss(self, request, pk=None):
        note = self.get_object()
        MatchState.objects.filter(ticket=note.ticket, load_id_value=note.snapshot.get("load_id")).update(dismissed=True)
        self.get_queryset().filter(ticket=note.ticket, snapshot__load_id=note.snapshot.get("load_id")).update(obsolete=True, read_at=timezone.now())
        return Response({"ok": True})


class PreferenceView(APIView):
    permission_classes = [IsDriver]

    def get(self, request):
        obj, _ = Preference.objects.get_or_create(owner=request.user)
        result = dict(PreferenceSerializer(obj).data)
        account = TelegramAccount.objects.filter(owner=request.user).first()
        result.update(telegram_connected=bool(account), telegram_blocked=bool(account and account.blocked), bot_configured=bool(os.getenv("DRIVER_BOT_TOKEN") and os.getenv("DRIVER_BOT_USERNAME")))
        return Response(result)

    def patch(self, request):
        obj, _ = Preference.objects.get_or_create(owner=request.user)
        serializer = PreferenceSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class TelegramLinkView(APIView):
    permission_classes = [IsDriver]

    def post(self, request):
        username = os.getenv("DRIVER_BOT_USERNAME", "").lstrip("@")
        if not username or not os.getenv("DRIVER_BOT_TOKEN"):
            return Response({"detail": "Telegram bot is not configured on the server."}, status=503)
        return Response({"url": f"https://t.me/{username}?start={new_link(request.user)}", "expires_in": 600})

    def delete(self, request):
        from .models import LinkToken
        TelegramAccount.objects.filter(owner=request.user).delete()
        LinkToken.objects.filter(owner=request.user).delete()
        return Response(status=204)
