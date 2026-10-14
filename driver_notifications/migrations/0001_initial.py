
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cargo', '0002_load_destination_lat_load_destination_lon_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BotCursor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40, unique=True)),
                ('offset', models.BigIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='LinkToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('digest', models.CharField(max_length=64, unique=True)),
                ('expires_at', models.DateTimeField()),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Preference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telegram_enabled', models.BooleanField(default=True)),
                ('partial_interval_minutes', models.PositiveSmallIntegerField(default=30)),
                ('quiet_start', models.TimeField(blank=True, null=True)),
                ('quiet_end', models.TimeField(blank=True, null=True)),
                ('timezone', models.CharField(default='Asia/Tashkent', max_length=64)),
                ('language', models.CharField(choices=[('uz', 'uz'), ('ru', 'ru')], default='uz', max_length=2)),
                ('owner', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TelegramAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chat_id', models.BigIntegerField(unique=True)),
                ('state', models.JSONField(default=dict)),
                ('blocked', models.BooleanField(default=False)),
                ('owner', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=120)),
                ('status', models.CharField(choices=[('active', 'active'), ('paused', 'paused'), ('closed', 'closed'), ('expired', 'expired')], default='active', max_length=12)),
                ('current_location', models.JSONField(default=dict)),
                ('origins', models.JSONField(default=list)),
                ('destinations', models.JSONField(default=list)),
                ('waypoints', models.JSONField(default=list)),
                ('route_mode', models.CharField(choices=[('alternatives', 'alternatives'), ('ordered', 'ordered'), ('anywhere', 'anywhere')], default='alternatives', max_length=20)),
                ('ready_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('available_tons', models.DecimalField(decimal_places=2, max_digits=8)),
                ('partial_load', models.BooleanField(default=False)),
                ('min_price', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('currency', models.CharField(choices=[('UZS', 'UZS'), ('USD', 'USD')], default='UZS', max_length=3)),
                ('price_basis', models.CharField(choices=[('trip', 'trip'), ('ton', 'ton')], default='trip', max_length=8)),
                ('match_mode', models.CharField(choices=[('route', 'route'), ('any_two', 'any_two'), ('full', 'full')], default='any_two', max_length=12)),
                ('notes', models.CharField(blank=True, max_length=1000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_key', models.CharField(max_length=180, unique=True)),
                ('kind', models.CharField(max_length=20)),
                ('level', models.CharField(blank=True, max_length=10)),
                ('snapshot', models.JSONField(default=dict)),
                ('reasons', models.JSONField(default=dict)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deliver_after', models.DateTimeField(db_index=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('delivery_error', models.CharField(blank=True, max_length=100)),
                ('message_id', models.BigIntegerField(blank=True, null=True)),
                ('message_chat_id', models.BigIntegerField(blank=True, null=True)),
                ('obsolete', models.BooleanField(default=False)),
                ('load', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='cargo.load')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='driver_notifications.ticket')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Vehicle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('kind', models.CharField(choices=[('tent', 'tent'), ('refrigerator', 'refrigerator'), ('flatbed', 'flatbed'), ('van', 'van'), ('tanker', 'tanker'), ('other', 'other')], max_length=30)),
                ('capacity_tons', models.DecimalField(decimal_places=2, max_digits=8)),
                ('volume_m3', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('plate', models.CharField(blank=True, max_length=20)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='ticket',
            name='vehicle',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='driver_notifications.vehicle'),
        ),
        migrations.CreateModel(
            name='MatchState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('load_id_value', models.BigIntegerField()),
                ('last_level', models.CharField(blank=True, max_length=10)),
                ('last_price', models.CharField(blank=True, max_length=100)),
                ('dismissed', models.BooleanField(default=False)),
                ('available', models.BooleanField(default=True)),
                ('sequence', models.PositiveIntegerField(default=0)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='driver_notifications.ticket')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('ticket', 'load_id_value'), name='one_driver_load_match')],
            },
        ),
    ]
