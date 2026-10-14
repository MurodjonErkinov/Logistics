from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def set_retention(apps, schema_editor):
    Entry = apps.get_model("telegram_import", "TelegramLoad")
    Post = apps.get_model("telegram_import", "TelegramPost")
    Load = apps.get_model("cargo", "Load")
    database = schema_editor.connection.alias
    now = timezone.now()
    for entry in Entry.objects.using(database).select_related("load", "post").exclude(load=None).iterator():
        expires_at = entry.load.created_at + timedelta(days=7)
        Entry.objects.using(database).filter(pk=entry.pk).update(expires_at=expires_at)
        if (expires_at > now and entry.status == "imported"
                and entry.post.status in ("imported", "review")
                and entry.post.expires_at <= now
                and entry.load.status == "closed"
                and entry.load.updated_at >= entry.post.expires_at):
            Load.objects.using(database).filter(pk=entry.load_id).update(status="open")
    for post in Post.objects.using(database).all().iterator():
        Post.objects.using(database).filter(pk=post.pk).update(expires_at=post.posted_at + timedelta(days=7))


class Migration(migrations.Migration):
    dependencies = [("telegram_import", "0004_telegrampost_provider")]
    operations = [
        migrations.AddField(
            model_name="telegramload", name="expires_at",
            field=models.DateTimeField(null=True, blank=True, db_index=True),
        ),
        migrations.RunPython(set_retention, migrations.RunPython.noop),
    ]
