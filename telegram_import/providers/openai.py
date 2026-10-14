import os

from ..schemas import INSTRUCTIONS, MessageExtraction


def extract_loads(text):
    from openai import OpenAI

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for Telegram import")
    client = OpenAI(timeout=30, max_retries=0)
    response = client.responses.parse(
        model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
        instructions=INSTRUCTIONS,
        input=text,
        text_format=MessageExtraction,
        store=False,
    )
    if response.output_parsed is None:
        raise RuntimeError("AI did not return a parsed result")
    return response.output_parsed
