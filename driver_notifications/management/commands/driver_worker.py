import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection

from driver_notifications.delivery import deliver
from driver_notifications.service import scan_all


class Command(BaseCommand):
    help = "Match driver tickets and deliver queued Telegram notifications"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            locked = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_try_advisory_lock(8239101)")
                    locked = cursor.fetchone()[0]
                if locked:
                    scan_all()
                    deliver()
            except Exception as exc:
                if options["once"]:
                    raise
                self.stderr.write(f"Driver worker: {type(exc).__name__}; retrying")
            finally:
                if locked:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_advisory_unlock(8239101)")
                close_old_connections()
            if options["once"]:
                return
            time.sleep(30)
