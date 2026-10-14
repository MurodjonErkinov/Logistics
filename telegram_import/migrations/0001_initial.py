import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cargo', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramCursor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chat_id', models.BigIntegerField(unique=True)),
                ('last_message_id', models.BigIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='TelegramPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chat_id', models.BigIntegerField()),
                ('message_id', models.BigIntegerField()),
                ('group_name', models.CharField(max_length=255)),
                ('text', models.TextField()),
                ('posted_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField()),
                ('status', models.CharField(choices=[('imported', 'Imported'), ('review', 'Review'), ('skipped', 'Skipped'), ('error', 'Error')], max_length=10)),
                ('detail', models.TextField(blank=True)),
                ('imported_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('load', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_post', to='cargo.load')),
            ],
            options={
                'ordering': ('-posted_at', '-id'),
                'constraints': [models.UniqueConstraint(fields=('chat_id', 'message_id'), name='unique_telegram_message')],
            },
        ),
    ]
