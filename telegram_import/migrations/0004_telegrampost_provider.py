from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_import', '0003_telegrampost_retry_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegrampost',
            name='provider',
            field=models.CharField(choices=[('openai', 'OpenAI'), ('ollama', 'Ollama')], default='openai', max_length=10),
        ),
    ]
