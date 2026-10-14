import os
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from driver_notifications.models import BotCursor
from driver_notifications.telegram import BotError, call, handle_update


class Command(BaseCommand):
    help = "Run the private driver Telegram bot using long polling"

    def handle(self, *args, **options):
        if not os.getenv("DRIVER_BOT_TOKEN"):
            raise CommandError("Set DRIVER_BOT_TOKEN in .env")
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(8239102)")
            if not cursor.fetchone()[0]:
                raise CommandError("Another driver bot is running")
        try:
            identity = call("getMe")
            self.stdout.write(f"Driver bot: @{identity['username']}")
            while True:
                row, _ = BotCursor.objects.get_or_create(name=str(identity["id"]))
                try:
                    updates = call("getUpdates", offset=row.offset, timeout=25, allowed_updates=["message", "callback_query"])
                    for update in updates:
                        try:
                            with transaction.atomic():
                                handle_update(update)
                                row.offset = update["update_id"] + 1
                                row.save(update_fields=["offset"])
                        except BotError:
                            raise
                        except Exception as exc:
                            self.stderr.write(f"Update {update['update_id']}: {type(exc).__name__}")
                            row.offset = update["update_id"] + 1
                            row.save(update_fields=["offset"])
                except BotError as exc:
                    self.stderr.write(str(exc))
                    time.sleep(max(5, min(60, exc.retry_after)))
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(8239102)")
