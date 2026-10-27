import os
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Load


def ttl_days():
    value = int(os.getenv("LOAD_TTL_DAYS", "14"))
    if value < 1:
        raise ValueError("LOAD_TTL_DAYS must be positive")
    return value


def close_stale_loads():
    """Close site-posted loads nobody has touched for a while or whose pickup date passed.

    Imported Telegram loads have their own expiry. Reopening or editing a load
    updates updated_at, so an owner can bring it back for another period.
    """
    now = timezone.now()
    today = timezone.localdate()
    start_of_today = timezone.make_aware(datetime.combine(today, time.min))
    return Load.objects.filter(status=Load.Status.OPEN, telegram_entry__isnull=True).filter(
        Q(updated_at__lt=now - timedelta(days=ttl_days()))
        | Q(pickup_date__lt=today, updated_at__lt=start_of_today)
    ).update(status=Load.Status.CLOSED, updated_at=now)
