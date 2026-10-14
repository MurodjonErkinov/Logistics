from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_import', '0002_multiple_loads'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegrampost',
            name='retry_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
