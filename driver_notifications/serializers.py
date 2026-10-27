import math
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from rest_framework import serializers

from .locations import checked_url
from .models import Notification, Preference, Ticket, Vehicle


class PlaceSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    source_url = serializers.URLField(max_length=2048, required=False)
    lat = serializers.FloatField(min_value=-90, max_value=90, required=False, allow_null=True)
    lon = serializers.FloatField(min_value=-180, max_value=180, required=False, allow_null=True)
    radius_km = serializers.FloatField(min_value=0, max_value=500, default=0)
    min_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)
    eta_hours = serializers.FloatField(min_value=0, max_value=720, default=0)
    priority = serializers.IntegerField(min_value=1, max_value=10, default=1)

    def validate_source_url(self, value):
        try:
            checked_url(value)
        except ValueError:
            raise serializers.ValidationError("Use a Google Maps or Yandex Maps link.") from None
        return value

    def validate(self, attrs):
        if (attrs.get("lat") is None) != (attrs.get("lon") is None):
            raise serializers.ValidationError("Both latitude and longitude are required.")
        for value in attrs.values():
            if isinstance(value, float) and not math.isfinite(value):
                raise serializers.ValidationError("Coordinates and distances must be finite.")
        if "min_price" in attrs:
            attrs["min_price"] = str(attrs["min_price"])
        return attrs


class LocationSerializer(PlaceSerializer):
    name = serializers.CharField(max_length=150, required=False, default="", allow_blank=True)


class VehicleSerializer(serializers.ModelSerializer):
    capacity_tons = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"))
    volume_m3 = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"), required=False, allow_null=True)

    class Meta:
        model = Vehicle
        fields = ["id", "name", "kind", "size_class", "capacity_tons", "volume_m3", "plate"]


class TicketSerializer(serializers.ModelSerializer):
    origins = PlaceSerializer(many=True)
    destinations = PlaceSerializer(many=True)
    waypoints = PlaceSerializer(many=True, required=False)
    current_location = LocationSerializer(required=False)
    available_tons = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"))
    min_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)
    vehicle_name = serializers.CharField(source="vehicle.name", read_only=True)

    class Meta:
        model = Ticket
        fields = ["id", "title", "vehicle", "vehicle_name", "status", "current_location", "origins", "destinations", "waypoints", "route_mode", "ready_at", "expires_at", "available_tons", "partial_load", "min_price", "currency", "price_basis", "match_mode", "notes", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        def value(key, default=None):
            return attrs.get(key, getattr(self.instance, key, default))
        vehicle = value("vehicle")
        if vehicle is None or vehicle.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError({"vehicle": "Choose your own vehicle."})
        if value("available_tons") > vehicle.capacity_tons:
            raise serializers.ValidationError({"available_tons": "Exceeds vehicle capacity."})
        now = timezone.now()
        expiry, ready = value("expires_at"), value("ready_at")
        if not expiry or not ready or expiry <= ready:
            raise serializers.ValidationError({"expires_at": "Expiry must follow ready time."})
        if value("status", "active") == "active" and (expiry <= now or expiry > now + timezone.timedelta(days=30)):
            raise serializers.ValidationError({"expires_at": "Active tickets expire within the next 30 days."})
        origins, destinations, waypoints = value("origins", []), value("destinations", []), value("waypoints", [])
        if not 1 <= len(origins) <= 10 or len(destinations) > 10 or len(waypoints) > 10:
            raise serializers.ValidationError("Use 1–10 origins and at most 10 destinations/waypoints.")
        if value("route_mode", "alternatives") != "anywhere" and not destinations:
            raise serializers.ValidationError({"destinations": "Choose at least one destination."})
        if value("route_mode") == "ordered" and (len(origins) != 1 or len(destinations) != 1):
            raise serializers.ValidationError("Ordered routes use one origin, intermediate waypoints and one destination.")
        return attrs


class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preference
        fields = ["telegram_enabled", "partial_interval_minutes", "quiet_start", "quiet_end", "timezone", "language"]
        read_only_fields = ["telegram_enabled"]

    def validate(self, attrs):
        if attrs.get("partial_interval_minutes", self.instance.partial_interval_minutes) not in (0, 15, 30, 60):
            raise serializers.ValidationError({"partial_interval_minutes": "Choose 0, 15, 30 or 60."})
        start = attrs.get("quiet_start", self.instance.quiet_start)
        end = attrs.get("quiet_end", self.instance.quiet_end)
        if bool(start) != bool(end) or (start and start == end):
            raise serializers.ValidationError("Specify both quiet hours with different start/end times.")
        try:
            ZoneInfo(attrs.get("timezone", self.instance.timezone))
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError({"timezone": "Unknown timezone."})
        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    obsolete = serializers.SerializerMethodField()

    def get_obsolete(self, obj):
        if obj.obsolete or obj.kind == "unavailable":
            return True
        if obj.kind in ("match", "price"):
            if obj.load is None or obj.load.status != "open":
                return True
            entry = getattr(obj.load, "telegram_entry", None)
            return bool(entry and entry.expires_at and entry.expires_at <= timezone.now())
        return False

    ticket_title = serializers.CharField(source="ticket.title", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "ticket", "ticket_title", "load", "kind", "level", "snapshot", "reasons", "read_at", "created_at", "obsolete", "sent_at", "delivery_error"]
        read_only_fields = fields
