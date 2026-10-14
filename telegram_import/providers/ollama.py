import json
import os
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import ValidationError

from ..schemas import INSTRUCTIONS, MessageExtraction


def validate_config():
    base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:4b").strip()
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
    if urlparse(base_url).scheme not in ("http", "https") or not urlparse(base_url).hostname:
        raise ValueError("OLLAMA_BASE_URL must be an HTTP URL")
    if not model or timeout <= 0:
        raise ValueError("Set a non-empty OLLAMA_MODEL and positive OLLAMA_TIMEOUT_SECONDS")
    return base_url, model, timeout


def read_stream(response, deadline):
    expired = threading.Event()

    def interrupt():
        expired.set()
        raw_socket = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if raw_socket is not None:
            try:
                raw_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    timer = threading.Timer(max(0, deadline - time.monotonic()), interrupt)
    timer.daemon = True
    timer.start()
    try:
        fragments = []
        result = {}
        for line in response:
            if expired.is_set() or time.monotonic() >= deadline:
                raise TimeoutError("Post parsing deadline exceeded")
            if not line.strip():
                continue
            chunk = json.loads(line)
            if chunk.get("error"):
                raise RuntimeError(f"Ollama error: {str(chunk['error'])[:500]}")
            fragments.append(chunk.get("message", {}).get("content", ""))
            if chunk.get("done") is True:
                result = chunk
                break
        if expired.is_set() or time.monotonic() >= deadline:
            raise TimeoutError("Post parsing deadline exceeded")
        result["message"] = {"content": "".join(fragments)}
        return result
    except (OSError, ValueError) as exc:
        if expired.is_set():
            raise TimeoutError("Post parsing deadline exceeded") from exc
        raise
    finally:
        timer.cancel()


def extract_loads(text):
    base_url, model, timeout = validate_config()
    max_seconds = float(os.getenv("OLLAMA_MAX_POST_SECONDS", "60"))
    if max_seconds <= 0:
        raise ValueError("OLLAMA_MAX_POST_SECONDS must be positive")
    deadline = time.monotonic() + max_seconds
    schema = MessageExtraction.model_json_schema()
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": INSTRUCTIONS + "\nReturn compact JSON without indentation. Keep notes short."},
            {"role": "user", "content": text},
        ],
        "format": schema,
        "stream": True,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_ctx": 4096, "num_batch": 128},
    }
    request = Request(base_url + "/api/chat", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=min(timeout, max_seconds)) as response:
            result = read_stream(response, deadline)
    except HTTPError as exc:
        try:
            error = json.loads(exc.read(2048)).get("error", "Server error")
        except (ValueError, AttributeError):
            error = "Server error"
        raise RuntimeError(f"Ollama HTTP {exc.code}: {str(error)[:500]}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Ollama post exceeded {max_seconds:g}s time limit; moving to the next message") from exc
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise RuntimeError(f"Ollama post exceeded {max_seconds:g}s time limit; moving to the next message") from exc
        raise RuntimeError("Cannot reach Ollama; check OLLAMA_BASE_URL and the Ollama service") from exc
    if result.get("error") or result.get("done") is not True or result.get("done_reason") == "length":
        raise RuntimeError("Ollama did not return a complete result")
    content = result.get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Ollama returned an empty result")
    try:
        return MessageExtraction.model_validate_json(content)
    except ValidationError as exc:
        raise RuntimeError("Ollama returned JSON that does not match the load schema") from exc
