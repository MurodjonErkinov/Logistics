import os

from .schemas import INSTRUCTIONS, LoadExtraction, MessageExtraction


def get_provider():
    provider = os.getenv("TELEGRAM_AI_PROVIDER", "openai").strip().lower()
    if provider != "openai":
        raise ValueError("Only TELEGRAM_AI_PROVIDER=openai is supported")
    return provider


def validate_provider():
    provider = get_provider()
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required when TELEGRAM_AI_PROVIDER=openai")
    return provider


def extract_loads(text):
    get_provider()
    from .providers.openai import extract_loads as extract
    return extract(text)
