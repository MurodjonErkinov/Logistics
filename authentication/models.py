import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager
from django.core.validators import RegexValidator
from django.db import models


class LogisticsUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "user", "User"
        DISPATCHER = "dispatcher", "Dispatcher"
        DRIVER = "driver", "Driver"
        ADMIN = "admin", "Admin"

    phone_number = models.CharField(
        max_length=16,
        blank=True,
        validators=[RegexValidator(r"^\+[1-9]\d{7,14}$", "Use international format, e.g. +998901234567.")],
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.USER)
    objects = LogisticsUserManager()


class RegistrationVerification(models.Model):
    """One active registration challenge per phone; rotating ID revokes old links."""

    phone_number = models.CharField(max_length=16, unique=True)
    verification_id = models.UUIDField(default=uuid.uuid4, unique=True)
    requested_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    chat_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    code_digest = models.CharField(max_length=64, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    bot_message_id = models.BigIntegerField(null=True, blank=True)


class PasswordResetVerification(models.Model):
    """A reset is bound to the existing account, Telegram chat and password."""

    phone_number = models.CharField(max_length=16, unique=True)
    verification_id = models.UUIDField(default=uuid.uuid4, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    chat_id = models.BigIntegerField(null=True, blank=True)
    password_fingerprint = models.CharField(max_length=64, blank=True)
    requested_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    code_digest = models.CharField(max_length=64, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    bot_message_id = models.BigIntegerField(null=True, blank=True)
