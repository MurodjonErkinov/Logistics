#!/usr/bin/env python3
"""Export local loads into one standalone script, then run it on production."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib

BUNDLE = ""  # Embedded by --export; contains cargo data, never credentials.


def inside_export():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from cargo.models import Load
    from django.core.serializers.json import DjangoJSONEncoder
    from django.forms.models import model_to_dict

    rows = []
    for load in Load.objects.select_related("posted_by", "telegram_entry__post").order_by("pk"):
        if load.company_id:
            raise RuntimeError("Company loads require explicit company mapping; export stopped.")
        data = model_to_dict(load, exclude=["id", "posted_by", "company"])
        data.update(created_at=load.created_at, updated_at=load.updated_at)
        entry = getattr(load, "telegram_entry", None)
        rows.append({"load": data, "username": load.posted_by.username,
                     "entry": model_to_dict(entry, exclude=["id", "post", "load"]) if entry else None,
                     "post": model_to_dict(entry.post, exclude=["id"]) if entry else None})
    print(json.dumps({"version": 1, "loads": rows}, cls=DjangoJSONEncoder))


def inside_import(dry_run):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_production")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from django.utils import timezone as dj_timezone
    from cargo.models import Load
    from telegram_import.models import TelegramLoad, TelegramPost
    from telegram_import.service import importer_user

    bundle = json.loads(zlib.decompress(base64.b64decode(BUNDLE)))
    if bundle.get("version") != 1:
        raise RuntimeError("Unsupported export version")

    def typed(model, data):
        return {key: model._meta.get_field(key).to_python(value) for key, value in data.items()}

    counts = {"created": 0, "existing": 0, "expired": 0}
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(8239103)")
        for row in bundle["loads"]:
            data = typed(Load, row["load"])
            post_data = typed(TelegramPost, row["post"]) if row["post"] else None
            entry_data = typed(TelegramLoad, row["entry"]) if row["entry"] else None
            post = None
            if post_data:
                expiry = entry_data.get("expires_at") or post_data["expires_at"]
                if expiry <= dj_timezone.now():
                    counts["expired"] += 1
                    continue
                post = TelegramPost.objects.filter(chat_id=post_data["chat_id"], message_id=post_data["message_id"]).first()
                if post and (TelegramLoad.objects.filter(post=post, position=entry_data["position"]).exists()
                             or post.status == TelegramPost.Status.SKIPPED):
                    counts["existing"] += 1
                    continue
            else:
                lookup = {k: v for k, v in data.items() if k not in ("created_at", "updated_at")}
                if Load.objects.filter(**lookup).exists():
                    counts["existing"] += 1
                    continue
            if post_data:
                owner = importer_user()
                if post is None:
                    post = TelegramPost.objects.create(**post_data)
            else:
                owner, created = get_user_model().objects.get_or_create(
                    username=row["username"], defaults={"is_active": False, "role": "user"})
                if created:
                    owner.set_unusable_password()
                    owner.save(update_fields=["password"])
            stamps = {k: data.pop(k) for k in ("created_at", "updated_at")}
            load = Load(posted_by=owner, **data)
            load.full_clean()
            load.save()
            Load.objects.filter(pk=load.pk).update(**stamps)
            if post_data:
                TelegramLoad.objects.create(post=post, load=load, **entry_data)
            counts["created"] += 1
        if dry_run:
            transaction.set_rollback(True)
    print(("DRY RUN (nothing saved): " if dry_run else "IMPORT COMPLETE: ") + json.dumps(counts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", metavar="OUTPUT", help="Build a standalone script from local Docker loads")
    parser.add_argument("--dry-run", action="store_true", help="Validate import and roll back without saving")
    parser.add_argument("--inside-export", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--inside-import", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside_export:
        return inside_export()
    if args.inside_import:
        return inside_import(args.dry_run)
    source = Path(__file__).read_text()
    if args.export:
        command = ["docker", "compose", "exec", "-T", "web", "python", "-", "--inside-export"]
        result = subprocess.run(command, input=source, text=True, capture_output=True, check=True)
        data = json.loads(result.stdout)
        encoded = base64.b64encode(zlib.compress(result.stdout.encode())).decode()
        output = Path(args.export)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Refuse to overwrite an earlier export.
        with output.open("x") as stream:
            os.chmod(output, 0o600)
            stream.write(source.replace('BUNDLE = ""  # Embedded', f'BUNDLE = {encoded!r}  # Embedded', 1))
        print(f"Exported {len(data['loads'])} loads: {output}")
        return
    if not BUNDLE:
        parser.error("No embedded loads. First run --export backups/import_local_loads.py locally.")
    if not Path(".env.production").is_file():
        parser.error("Run from the server project directory containing .env.production.")
    compose = ["docker", "compose", "--project-name", "logistics-prod", "--env-file", ".env.production", "-f", "compose.production.yaml"]
    subprocess.run(compose + ["exec", "-T", "web", "python", "-c", "import django; django.setup()"], check=True)
    if not args.dry_run:
        backup_dir = Path("backups")
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        backup = backup_dir / ("before-load-import-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".dump")
        with backup.open("xb") as stream:
            os.chmod(backup, 0o600)
            subprocess.run(compose + ["exec", "-T", "db", "sh", "-c", 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'], stdout=stream, check=True)
        print(f"Database backup: {backup}", flush=True)
    command = compose + ["exec", "-T", "web", "python", "-", "--inside-import"]
    if args.dry_run:
        command.append("--dry-run")
    subprocess.run(command, input=source, text=True, check=True)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)
