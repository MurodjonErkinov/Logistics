import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from cargo.maintenance import close_stale_loads
from telegram_import.service import delete_expired_loads


class Command(BaseCommand):
    help = "Delete expired Telegram cargo and close stale site-posted loads"

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")

    def handle(self, *args, **options):
        while True:
            try:
                close_old_connections()
                count = delete_expired_loads()
                if count or not options["watch"]:
                    self.stdout.write(f"Deleted expired Telegram loads: {count}")
                closed = close_stale_loads()
                if closed or not options["watch"]:
                    self.stdout.write(f"Closed stale site loads: {closed}")
            except Exception as exc:
                if not options["watch"]:
                    raise
                self.stderr.write(f"Cleanup failed: {type(exc).__name__}; retrying in 60 seconds")
            finally:
                close_old_connections()
            if not options["watch"]:
                return
            time.sleep(60)
