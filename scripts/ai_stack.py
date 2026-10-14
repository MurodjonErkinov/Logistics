import argparse
import fcntl
import os
from pathlib import Path
import shlex
import stat
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


def read_env():
    if not ENV_FILE.exists():
        raise ValueError("Create .env from .env.example first")
    values = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        values[key.strip()] = value
    return values


def save_selection(provider, ollama):
    updates = {"TELEGRAM_AI_PROVIDER": provider, **ollama}
    lines = []
    for line in ENV_FILE.read_text().splitlines():
        key = line.partition("=")[0].strip()
        if key in updates:
            if updates[key] is not None:
                lines.append(f"{key}={updates[key]}")
                updates[key] = None
        else:
            lines.append(line)
    lines.extend(f"{key}={value}" for key, value in updates.items() if value is not None)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=ROOT, prefix=".env.", delete=False) as output:
            temporary = Path(output.name)
            output.write("\n".join(lines) + "\n")
        temporary.chmod(stat.S_IMODE(ENV_FILE.stat().st_mode))
        temporary.replace(ENV_FILE)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def start_stack(action, provider=None, compose="docker compose"):
    values = read_env()
    provider = provider or os.getenv("TELEGRAM_AI_PROVIDER", values.get("TELEGRAM_AI_PROVIDER", "openai"))
    if provider not in ("openai", "ollama"):
        raise ValueError("Select openai or ollama")
    defaults = {"OLLAMA_BASE_URL": "http://ollama:11434", "OLLAMA_MODEL": "qwen3:4b", "OLLAMA_TIMEOUT_SECONDS": "600"}
    ollama = {key: os.getenv(key, values.get(key, default)) for key, default in defaults.items()}
    environment = {**os.environ, "TELEGRAM_AI_PROVIDER": provider, **ollama}
    prefix = shlex.split(compose)

    def run(*arguments):
        subprocess.run([*prefix, *arguments], cwd=ROOT, env=environment, check=True)

    if action == "build":
        run("build", "web")
    managed_ollama = provider == "ollama" and ollama["OLLAMA_BASE_URL"].rstrip("/") == "http://ollama:11434"
    if managed_ollama:
        run("--profile", "ollama", "up", "-d", "--wait", "ollama")
        if action == "build":
            run("exec", "-T", "ollama", "ollama", "pull", ollama["OLLAMA_MODEL"])
    configured = all(values.get(key) for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_GROUP"))
    if configured:
        run("run", "--rm", "--no-deps", "-T", "telegram_importer", "python", "manage.py", "check_ai_provider")
    run("stop", "telegram_importer")
    run("up", "-d", "--wait", "--force-recreate", "web")
    run("exec", "-T", "web", "python", "manage.py", "migrate", "--noinput")
    run("up", "-d", "--no-deps", "--force-recreate", "telegram_cleanup", "driver_worker")
    save_selection(provider, ollama)
    if configured:
        run("--profile", "telegram", "up", "-d", "--no-deps", "--force-recreate", "telegram_importer")
    if not managed_ollama:
        run("--profile", "ollama", "stop", "ollama")
    print(f"Selected AI provider: {provider}", flush=True)
    if not configured:
        print("Backend is running. Configure Telegram credentials and login, then run make telegram-up.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "up"))
    parser.add_argument("--provider", choices=("openai", "ollama"))
    parser.add_argument("--compose", default="docker compose")
    args = parser.parse_args()
    with (ROOT / ".ai-stack.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, "Another provider switch is running; wait for it to finish.\n")
        try:
            start_stack(args.action, args.provider, args.compose)
        except (ValueError, OSError) as exc:
            parser.exit(1, f"{exc}\n")
        except subprocess.CalledProcessError:
            parser.exit(1, "Docker operation failed; provider switch did not complete.\n")


if __name__ == "__main__":
    main()
