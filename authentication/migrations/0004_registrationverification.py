import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("authentication", "0003_alter_user_managers_user_phone_number_user_role")]
    operations = [
        migrations.CreateModel(
            name="RegistrationVerification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone_number", models.CharField(max_length=16, unique=True)),
                ("verification_id", models.UUIDField(default=uuid.uuid4, unique=True)),
                ("requested_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("chat_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("code_digest", models.CharField(blank=True, max_length=64)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("bot_message_id", models.BigIntegerField(blank=True, null=True)),
            ],
        ),
    ]
