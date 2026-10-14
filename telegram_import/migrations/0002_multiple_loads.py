import django.db.models.deletion
from django.db import migrations, models


def copy_existing_loads(apps, schema_editor):
    Post = apps.get_model('telegram_import', 'TelegramPost')
    Entry = apps.get_model('telegram_import', 'TelegramLoad')
    database = schema_editor.connection.alias
    for post in Post.objects.using(database).exclude(load_id=None).iterator():
        Entry.objects.using(database).create(
            post_id=post.pk, position=0, load_id=post.load_id,
            status=post.status, detail=post.detail,
        )


def restore_single_loads(apps, schema_editor):
    Post = apps.get_model('telegram_import', 'TelegramPost')
    Entry = apps.get_model('telegram_import', 'TelegramLoad')
    database = schema_editor.connection.alias
    linked = Entry.objects.using(database).exclude(load_id=None)
    if linked.values('post_id').annotate(total=models.Count('id')).filter(total__gt=1).exists():
        raise RuntimeError('Cannot reverse migration while a Telegram post has multiple loads')
    for entry in linked.iterator():
        Post.objects.using(database).filter(pk=entry.post_id).update(load_id=entry.load_id)


class Migration(migrations.Migration):

    dependencies = [
        ('cargo', '0001_initial'),
        ('telegram_import', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='telegrampost',
            name='status',
            field=models.CharField(choices=[('processing', 'Processing'), ('imported', 'Imported'), ('review', 'Review'), ('skipped', 'Skipped'), ('error', 'Error')], max_length=10),
        ),
        migrations.CreateModel(
            name='TelegramLoad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('processing', 'Processing'), ('imported', 'Imported'), ('review', 'Review'), ('skipped', 'Skipped'), ('error', 'Error')], max_length=10)),
                ('payload', models.JSONField(default=dict)),
                ('detail', models.TextField(blank=True)),
                ('load', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_entry', to='cargo.load')),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='telegram_import.telegrampost')),
            ],
            options={
                'ordering': ('position',),
                'constraints': [models.UniqueConstraint(fields=('post', 'position'), name='unique_telegram_load_position')],
            },
        ),
        migrations.RunPython(copy_existing_loads, restore_single_loads),
        migrations.RemoveField(
            model_name='telegrampost',
            name='load',
        ),
    ]
