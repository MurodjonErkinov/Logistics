import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError

from telegram_import.extraction import validate_provider
from telegram_import.providers.ollama import validate_config


class Command(BaseCommand):
    help = "Check selected parser configuration without sending a message to AI"

    def handle(self, *args, **options):
        try:
            provider = validate_provider()
            if provider == "ollama":
                base_url, model, _ = validate_config()
                with urlopen(base_url + "/api/tags", timeout=15) as response:
                    models = json.load(response).get("models", [])
                model_name = model if ":" in model else model + ":latest"
                if not any(item.get("name") == model_name or item.get("model") == model_name for item in models):
                    raise ValueError(f"Pull the Ollama model first: {model}")
        except (ValueError, HTTPError, URLError, TimeoutError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"AI provider ready: {provider}")
