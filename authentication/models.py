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
