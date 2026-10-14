from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_import', '0005_load_retention'),
    ]

    operations = [
        migrations.AlterField(
            model_name='telegrampost',
            name='provider',
            field=models.CharField(choices=[('openai', 'OpenAI')], default='openai', max_length=10),
        ),
    ]
