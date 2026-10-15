from django.conf import settings
from django.db import models
from cargo.vehicle_catalog import BODY_CHOICES, SIZE_CHOICES


class Vehicle(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=30, choices=BODY_CHOICES)
    size_class = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True, default="")
    capacity_tons = models.DecimalField(max_digits=8, decimal_places=2)
    volume_m3 = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    plate = models.CharField(max_length=20, blank=True)


class Ticket(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    title = models.CharField(max_length=120)
    status = models.CharField(max_length=12, default="active", choices=[(x, x) for x in ("active", "paused", "closed", "expired")])
    current_location = models.JSONField(default=dict)
    origins = models.JSONField(default=list)
    destinations = models.JSONField(default=list)
    waypoints = models.JSONField(default=list)
    route_mode = models.CharField(max_length=20, default="alternatives", choices=[(x, x) for x in ("alternatives", "ordered", "anywhere")])
    ready_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    available_tons = models.DecimalField(max_digits=8, decimal_places=2)
    partial_load = models.BooleanField(default=False)
    min_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="UZS", choices=[("UZS", "UZS"), ("USD", "USD")])
    price_basis = models.CharField(max_length=8, default="trip", choices=[("trip", "trip"), ("ton", "ton")])
    match_mode = models.CharField(max_length=12, default="any_two", choices=[("route", "route"), ("any_two", "any_two"), ("full", "full")])
    notes = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class Preference(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    telegram_enabled = models.BooleanField(default=True)
    partial_interval_minutes = models.PositiveSmallIntegerField(default=30)
    quiet_start = models.TimeField(null=True, blank=True)
    quiet_end = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Tashkent")
    language = models.CharField(max_length=2, default="uz", choices=[("uz", "uz"), ("ru", "ru")])


class TelegramAccount(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    chat_id = models.BigIntegerField(unique=True)
    state = models.JSONField(default=dict)
    ui = models.JSONField(default=dict, blank=True)
    blocked = models.BooleanField(default=False)


class LinkToken(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()


class MatchState(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    load_id_value = models.BigIntegerField()
    last_level = models.CharField(max_length=10, blank=True)
    last_price = models.CharField(max_length=100, blank=True)
    dismissed = models.BooleanField(default=False)
    available = models.BooleanField(default=True)
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ticket", "load_id_value"], name="one_driver_load_match")]


class Notification(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    load = models.ForeignKey("cargo.Load", null=True, blank=True, on_delete=models.SET_NULL)
    event_key = models.CharField(max_length=180, unique=True)
    kind = models.CharField(max_length=20)
    level = models.CharField(max_length=10, blank=True)
    snapshot = models.JSONField(default=dict)
    reasons = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deliver_after = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    delivery_error = models.CharField(max_length=100, blank=True)
    message_id = models.BigIntegerField(null=True, blank=True)
    message_chat_id = models.BigIntegerField(null=True, blank=True)
    obsolete = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


class BotCursor(models.Model):
    name = models.CharField(max_length=40, unique=True)
    offset = models.BigIntegerField(default=0)
