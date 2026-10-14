import os
import re
from datetime import timedelta, timezone as datetime_timezone
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from cargo.models import Load
from cargo.serializers import LoadSerializer

from .extraction import extract_loads, get_provider
from .filtering import looks_like_load
from .models import TelegramCursor, TelegramLoad, TelegramPost


def ttl_hours():
    value = int(os.getenv("TELEGRAM_LOAD_TTL_HOURS", "168"))
    if value < 1:
        raise ValueError("TELEGRAM_LOAD_TTL_HOURS must be positive")
    return value


def importer_user():
    model = get_user_model()
    user, created = model.objects.get_or_create(
        username="telegram_importer",
        defaults={"is_active": False, "email": "", "role": model.Role.USER},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif user.is_active or user.has_usable_password():
        raise RuntimeError("Reserved telegram_importer account is in use")
    return user


def mark_cursor(chat_id, message_id):
    cursor, _ = TelegramCursor.objects.get_or_create(chat_id=chat_id)
    if message_id > cursor.last_message_id:
        cursor.last_message_id = message_id
        cursor.save(update_fields=["last_message_id"])


def rate_limit_delay(message, headers=None):
    headers = headers or {}
    try:
        seconds = float(headers.get("retry-after", ""))
        if seconds > 0:
            return timedelta(seconds=seconds + 1)
    except (TypeError, ValueError):
        pass
    match = re.search(r"try again in ([\d.dhms]+)", message, re.IGNORECASE)
    if match:
        units = {"d": 86400, "h": 3600, "m": 60, "s": 1, "ms": 0.001}
        seconds = sum(float(value) * units[unit] for value, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|d|h|m|s)", match[1]))
        if seconds > 0:
            return timedelta(seconds=seconds + 1)
    return timedelta(hours=1) if "insufficient_quota" in message else timedelta(seconds=60)


def ai_cooldown():
    if get_provider() == "ollama":
        return None
    return TelegramPost.objects.filter(provider=get_provider(), status=TelegramPost.Status.ERROR, retry_at__gt=timezone.now()).order_by("-retry_at").values_list("retry_at", flat=True).first()


def close_entries(entries):
    return Load.objects.filter(telegram_entry__in=entries, status=Load.Status.OPEN).update(
        status=Load.Status.CLOSED, updated_at=timezone.now(),
    )


def load_payload(extracted):
    return {
        "origin": extracted.origin,
        "destination": extracted.destination,
        "cargo_name": extracted.cargo_name,
        "vehicle_type": extracted.vehicle_type,
        "weight_tons": str(extracted.weight_tons) if extracted.weight_tons is not None else None,
        "is_price_negotiable": extracted.is_price_negotiable,
        "price_amount": str(extracted.price_amount) if extracted.price_amount is not None else None,
        "currency": extracted.currency or "UZS",
        "contact_phone": extracted.contact_phone,
        "alternate_phone": extracted.alternate_phone or "",
        "pickup_date": extracted.pickup_date,
        "notes": extracted.notes or "",
        "status": Load.Status.OPEN,
    }


def save_entry(post, position, extracted, user):
    entry, _ = TelegramLoad.objects.get_or_create(
        post=post, position=position, defaults={"status": TelegramPost.Status.REVIEW},
    )
    if entry.expires_at and entry.expires_at <= timezone.now():
        return entry
    entry.payload = extracted.model_dump(mode="json")
    payload = load_payload(extracted)
    missing = [field for field in ("origin", "destination", "cargo_name", "vehicle_type", "weight_tons", "contact_phone") if not payload[field]]
    serializer = LoadSerializer(instance=entry.load, data=payload, context={"request": SimpleNamespace(user=user)})
    if extracted.price_amount is not None and extracted.currency is None:
        entry.detail = "Price currency is unclear"
    elif missing:
        entry.detail = "Missing: " + ", ".join(missing)
    elif not serializer.is_valid():
        entry.detail = str(serializer.errors)[:1000]
    else:
        entry.load = serializer.save(posted_by=user) if entry.load_id is None else serializer.save()
        if entry.expires_at is None:
            entry.expires_at = entry.load.created_at + timedelta(days=7)
        entry.detail = ""
    entry.status = TelegramPost.Status.REVIEW if entry.detail else TelegramPost.Status.IMPORTED
    if entry.status == TelegramPost.Status.REVIEW:
        close_entries(TelegramLoad.objects.filter(pk=entry.pk))
    entry.save(update_fields=["load", "payload", "status", "detail", "expires_at"])
    return entry


def capture_message(chat_id, message_id, group_name, text, posted_at):
    text = (text or "").strip()
    posted_at = posted_at if timezone.is_aware(posted_at) else timezone.make_aware(posted_at, datetime_timezone.utc)
    with transaction.atomic():
        existing = TelegramPost.objects.select_for_update().filter(chat_id=chat_id, message_id=message_id).first()
        if existing and existing.text == text:
            mark_cursor(chat_id, message_id)
            return existing
        post, _ = TelegramPost.objects.update_or_create(
            chat_id=chat_id, message_id=message_id,
            defaults={"group_name": group_name, "text": text, "posted_at": posted_at,
                      "expires_at": posted_at + timedelta(hours=ttl_hours()),
                      "provider": get_provider(), "status": TelegramPost.Status.PROCESSING,
                      "detail": "Queued for parsing", "retry_at": None},
        )
        close_entries(post.entries.all())
        mark_cursor(chat_id, message_id)
        return post


def ingest_message(chat_id, message_id, group_name, text, posted_at, expected_revision=None):
    posted_at = posted_at if timezone.is_aware(posted_at) else timezone.make_aware(posted_at, datetime_timezone.utc)
    expires_at = posted_at + timedelta(hours=ttl_hours())
    text = (text or "").strip()
    with transaction.atomic():
        existing = TelegramPost.objects.select_for_update().filter(chat_id=chat_id, message_id=message_id).first()
        if expected_revision is not None and (existing is None or existing.updated_at != expected_revision):
            return existing
        if existing and existing.text == text and existing.provider == get_provider() and existing.status == TelegramPost.Status.ERROR and existing.retry_at and existing.retry_at > timezone.now():
            mark_cursor(chat_id, message_id)
            return existing
        if existing and existing.text == text and existing.status not in (TelegramPost.Status.ERROR, TelegramPost.Status.PROCESSING):
            mark_cursor(chat_id, message_id)
            return existing

        cooldown = ai_cooldown()
        post, _ = TelegramPost.objects.update_or_create(
            chat_id=chat_id, message_id=message_id,
            defaults={"group_name": group_name, "text": text, "posted_at": posted_at,
                      "expires_at": expires_at, "provider": get_provider(), "status": TelegramPost.Status.PROCESSING, "detail": ""},
        )
    revision = post.updated_at
    offers = []
    retry_at = None
    status = TelegramPost.Status.SKIPPED
    if not text or expires_at <= timezone.now():
        detail = "Empty or expired message"
    elif os.getenv("TELEGRAM_PREFILTER_ENABLED", "true").lower() in ("true", "1", "yes") and not looks_like_load(text):
        detail = "No freight or route hints; AI not called"
    else:
        if cooldown:
            status = TelegramPost.Status.ERROR
            retry_at = cooldown
            detail = f"AI paused until {cooldown.isoformat()}; message saved for retry"
        else:
            try:
                offers = extract_loads(text).loads
                detail = "Not a load offer" if not offers else ""
            except Exception as exc:
                status = TelegramPost.Status.ERROR
                detail = str(exc)[:1000]
                delay = rate_limit_delay(str(exc), getattr(getattr(exc, "response", None), "headers", None)) if getattr(exc, "status_code", None) == 429 else timedelta(hours=1) if "time limit; moving to the next message" in str(exc) else timedelta(seconds=60)
                retry_at = timezone.now() + delay

    with transaction.atomic():
        post = TelegramPost.objects.select_for_update().get(pk=post.pk)
        if post.updated_at != revision:
            return post
        if post.expires_at <= timezone.now():
            offers = []
            status = TelegramPost.Status.SKIPPED
            detail = "Expired message"
            retry_at = None
        if offers:
            user = importer_user()
            entries = [save_entry(post, position, offer, user) for position, offer in enumerate(offers)]
            removed = post.entries.filter(position__gte=len(offers))
            close_entries(removed)
            removed.update(status=TelegramPost.Status.SKIPPED, detail="Offer removed from source message")
            imported = sum(entry.status == TelegramPost.Status.IMPORTED for entry in entries)
            review = len(entries) - imported
            status = TelegramPost.Status.REVIEW if review else TelegramPost.Status.IMPORTED
            detail = f"Imported: {imported}; review: {review}"
        else:
            close_entries(post.entries.all())
            post.entries.update(status=status, detail=detail)
        post.status = status
        post.detail = detail
        post.retry_at = retry_at
        post.save(update_fields=["status", "detail", "retry_at", "updated_at"])
        mark_cursor(chat_id, message_id)
    return post


def retry_failed_messages(chat_id, limit=1, on_result=None):
    if ai_cooldown():
        return 0
    now = timezone.now()
    posts = list(TelegramPost.objects.filter(
        chat_id=chat_id, status__in=(TelegramPost.Status.ERROR, TelegramPost.Status.PROCESSING),
        expires_at__gt=now,
    ).filter(~Q(provider=get_provider()) | Q(retry_at__isnull=True) | Q(retry_at__lte=now)).order_by("-posted_at")[:limit])
    count = 0
    for post in posts:
        result = ingest_message(post.chat_id, post.message_id, post.group_name, post.text, post.posted_at, expected_revision=post.updated_at)
        if on_result and result is not None:
            on_result(result)
        count += 1
        if ai_cooldown():
            break
    return count


def delete_expired_loads():
    with transaction.atomic():
        entries = list(TelegramLoad.objects.select_for_update().filter(
            expires_at__lte=timezone.now(), load__isnull=False,
        ))
        load_ids = [entry.load_id for entry in entries]
        _, counts = Load.objects.filter(pk__in=load_ids).delete()
        TelegramLoad.objects.filter(pk__in=[entry.pk for entry in entries]).update(
            status=TelegramPost.Status.SKIPPED, detail="Deleted after 7 days", payload={},
        )
        return counts.get("cargo.Load", 0)


def close_deleted_messages(chat_id, message_ids):
    with transaction.atomic():
        posts = TelegramPost.objects.filter(chat_id=chat_id, message_id__in=message_ids)
        entries = TelegramLoad.objects.filter(post__in=posts)
        close_entries(entries)
        entries.update(status=TelegramPost.Status.SKIPPED, detail="Source message deleted")
        posts.update(status=TelegramPost.Status.SKIPPED, detail="Source message deleted", updated_at=timezone.now())
