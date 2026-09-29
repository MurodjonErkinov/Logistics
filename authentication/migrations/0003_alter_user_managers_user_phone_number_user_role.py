import authentication.models
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_remove_user_profile_image'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='user',
            managers=[
                ('objects', authentication.models.LogisticsUserManager()),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=16, validators=[django.core.validators.RegexValidator('^\\+[1-9]\\d{7,14}$', 'Use international format, e.g. +998901234567.')]),
        ),
        migrations.AddField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('user', 'User'), ('dispatcher', 'Dispatcher'), ('driver', 'Driver'), ('admin', 'Admin')], default='user', max_length=16),
        ),
    ]
