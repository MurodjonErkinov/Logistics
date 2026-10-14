import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Log in to the Telegram account and save its session"

    def handle(self, *args, **options):
        from telethon.sync import TelegramClient

        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        if not api_id or not api_hash:
            raise CommandError("Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")
        session = "/app/.telegram_session/importer"
        os.makedirs(os.path.dirname(session), exist_ok=True)
        with TelegramClient(session, int(api_id), api_hash) as client:
            self.stdout.write(f"Logged in as {client.get_me().username or client.get_me().id}")
