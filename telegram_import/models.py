from django.db import models

from cargo.models import Load


class TelegramPost(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        IMPORTED = "imported", "Imported"
        REVIEW = "review", "Review"
        SKIPPED = "skipped", "Skipped"
        ERROR = "error", "Error"

    chat_id = models.BigIntegerField()
    message_id = models.BigIntegerField()
    group_name = models.CharField(max_length=255)
    text = models.TextField()
    posted_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices)
    provider = models.CharField(max_length=10, choices=(("openai", "OpenAI"),), default="openai")
    detail = models.TextField(blank=True)
    retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("chat_id", "message_id"), name="unique_telegram_message")]
        ordering = ("-posted_at", "-id")

    @property
    def source_url(self):
        name = self.group_name.removeprefix("https://t.me/").removeprefix("http://t.me/").lstrip("@/").split("/")[0]
        return f"https://t.me/{name}/{self.message_id}" if name else None


class TelegramCursor(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    last_message_id = models.BigIntegerField(default=0)


class TelegramLoad(models.Model):
    post = models.ForeignKey(TelegramPost, on_delete=models.CASCADE, related_name="entries")
    position = models.PositiveIntegerField()
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    load = models.OneToOneField(Load, on_delete=models.SET_NULL, null=True, blank=True, related_name="telegram_entry")
    status = models.CharField(max_length=10, choices=TelegramPost.Status.choices)
    payload = models.JSONField(default=dict)
    detail = models.TextField(blank=True)

    class Meta:
        ordering = ("position",)
        constraints = [models.UniqueConstraint(fields=("post", "position"), name="unique_telegram_load_position")]
