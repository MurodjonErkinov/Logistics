from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from partners.models import Company


phone_validator = RegexValidator(
    r"^(?:\+[1-9]\d{7,14}|[1-9]\d{8})$",
    "Use a 9-digit local number or international format such as +998938086599.",
)


class Load(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    class Currency(models.TextChoices):
        UZS = "UZS", "UZS"
        USD = "USD", "USD"

    origin = models.CharField(max_length=150)
    destination = models.CharField(max_length=150)
    cargo_name = models.CharField(max_length=255)
    vehicle_type = models.CharField(max_length=120)
    weight_tons = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    is_price_negotiable = models.BooleanField(default=True)
    price_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.UZS)
    contact_phone = models.CharField(max_length=16, validators=[phone_validator])
    alternate_phone = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    pickup_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posted_loads")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="loads")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_price_negotiable=True) | models.Q(price_amount__isnull=False),
                name="load_price_or_negotiable",
            ),
        ]

    def __str__(self):
        return f"{self.origin} → {self.destination}: {self.cargo_name}"

    @property
    def display_text(self):
        weight = format(self.weight_tons.normalize(), "f")
        lines = [
            f"🚛 {self.origin.upper()} ➡️ {self.destination.upper()} 🚛",
            "",
            f"📦 YUK: {self.cargo_name.upper()}",
            "",
            f"🚚 {self.vehicle_type.upper()} KERAK",
            "",
            f"⚖️ OG‘IRLIGI: {weight} TONNA",
            "",
        ]
        if self.price_amount is None:
            lines.append("💰 NARX KELISHILADI!")
        else:
            amount = format(self.price_amount.normalize(), "f")
            amount = f"{Decimal(amount):,.0f}".replace(",", " ") if self.price_amount % 1 == 0 else amount
            suffix = " (KELISHILADI)" if self.is_price_negotiable else ""
            lines.append(f"💰 NARX: {amount} {self.currency}{suffix}")
        if self.pickup_date:
            lines.extend(("", f"📅 YUKLASH: {self.pickup_date:%d.%m.%Y}"))
        if self.notes:
            lines.extend(("", f"📝 {self.notes}"))
        if self.company_id:
            lines.extend(("", f"🏢 {self.company.name}"))
        lines.extend(("", "━━━━━━━━━━━━━━━━━━", "", f"📞 {self.contact_phone}"))
        if self.alternate_phone:
            lines.extend(("", f"📞 {self.alternate_phone}"))
        return "\n".join(lines)
