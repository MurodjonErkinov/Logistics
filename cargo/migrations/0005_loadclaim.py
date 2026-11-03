from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("cargo", "0004_load_vehicle_kind_load_vehicle_size"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="LoadClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="load_claims", to=settings.AUTH_USER_MODEL)),
                ("load", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="claims", to="cargo.load")),
            ],
            options={"ordering": ("-created_at", "-id"), "constraints": [models.UniqueConstraint(fields=("load", "driver"), name="unique_driver_load_claim")]},
        ),
    ]
