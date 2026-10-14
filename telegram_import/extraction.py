import os

from .schemas import INSTRUCTIONS, LoadExtraction, MessageExtraction


def get_provider():
    provider = os.getenv("TELEGRAM_AI_PROVIDER", "openai").strip().lower()
    if provider not in ("openai", "ollama"):
        raise ValueError("TELEGRAM_AI_PROVIDER must be openai or ollama")
    return provider


def validate_provider():
    provider = get_provider()
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required when TELEGRAM_AI_PROVIDER=openai")
    if provider == "ollama":
        from .providers.ollama import validate_config

        validate_config()
    return provider


def extract_loads(text):
    if get_provider() == "openai":
        from .providers.openai import extract_loads as extract
    else:
        from .providers.ollama import extract_loads as extract
    return extract(text)

