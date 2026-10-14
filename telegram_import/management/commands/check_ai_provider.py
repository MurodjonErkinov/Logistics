from django.core.management.base import BaseCommand, CommandError
from telegram_import.extraction import validate_provider


class Command(BaseCommand):
    help = "Check OpenAI parser configuration without sending a message to AI"

    def handle(self, *args, **options):
        try:
            provider = validate_provider()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"AI provider ready: {provider}")
