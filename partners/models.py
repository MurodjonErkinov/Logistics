from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(
        max_length=16,
        blank=True,
        validators=[RegexValidator(r"^\+[1-9]\d{7,14}$", "Use international format, e.g. +998901234567.")],
    )
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_companies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class CompanyMember(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    can_post_cargo = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("company", "user"), name="unique_company_member")]

    def __str__(self):
        return f"{self.user} @ {self.company}"
