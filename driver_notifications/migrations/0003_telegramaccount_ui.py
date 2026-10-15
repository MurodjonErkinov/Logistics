from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("driver_notifications", "0002_vehicle_size_class_alter_vehicle_kind")]

    operations = [
        migrations.AddField(
            model_name="telegramaccount",
            name="ui",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
