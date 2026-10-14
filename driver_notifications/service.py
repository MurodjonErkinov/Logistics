import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from cargo.models import Load
from .matching import evaluate
from .models import LinkToken, MatchState, Notification, Preference, TelegramAccount, Ticket


def new_link(user):
    token = secrets.token_urlsafe(24)
    LinkToken.objects.filter(owner=user).delete()
    LinkToken.objects.create(owner=user, digest=hashlib.sha256(token.encode()).hexdigest(), expires_at=timezone.now() + timedelta(minutes=10))
    return token


@transaction.atomic
def bind_account(token, chat_id):
    row = LinkToken.objects.select_for_update().filter(digest=hashlib.sha256(token.encode()).hexdigest(), expires_at__gt=timezone.now(), owner__role="driver", owner__is_active=True).first()
    if not row or TelegramAccount.objects.filter(chat_id=chat_id).exclude(owner=row.owner).exists():
        return None
    account, _ = TelegramAccount.objects.update_or_create(owner=row.owner, defaults={"chat_id": chat_id, "blocked": False, "state": {}})
    row.delete()
    return account


def snapshot(load):
    return {"load_id": load.pk, "origin": load.origin, "destination": load.destination, "cargo_name": load.cargo_name, "phone": load.contact_phone, "price": str(load.price_amount) if load.price_amount is not None else None, "currency": load.currency, "price_basis": load.price_basis, "weight_tons": str(load.weight_tons), "vehicle_type": load.vehicle_type}


def notify(ticket, kind, key, load=None, result=None, data=None):
    pref, _ = Preference.objects.get_or_create(owner=ticket.owner)
    result = result or {}
    delay = pref.partial_interval_minutes if result.get("level") == "partial" else 0
    return Notification.objects.get_or_create(event_key=key, defaults={"owner": ticket.owner, "ticket": ticket, "load": load, "kind": kind, "level": result.get("level", ""), "snapshot": data or (snapshot(load) if load else {}), "reasons": result, "deliver_after": timezone.now() + timedelta(minutes=delay)})


@transaction.atomic
def scan_ticket(ticket_id):
    ticket = Ticket.objects.select_for_update().select_related("owner", "vehicle").get(pk=ticket_id)
    now = timezone.now()
    if ticket.owner.role != "driver" or not ticket.owner.is_active:
        return
    if ticket.status not in ("closed", "expired") and ticket.expires_at <= now:
        ticket.status = "expired"
        ticket.save(update_fields=["status", "updated_at"])
    if ticket.status == "expired":
        notify(ticket, "expired", f"expiry:{ticket.pk}:{ticket.expires_at.isoformat()}")
        return
    if ticket.status != "active":
        return
    if ticket.expires_at - now <= timedelta(hours=2):
        notify(ticket, "expiring", f"reminder:{ticket.pk}:{ticket.expires_at.isoformat()}")
    loads = Load.objects.filter(status="open").filter(Q(telegram_entry__expires_at__isnull=True) | Q(telegram_entry__expires_at__gt=now))
    available = set()
    for load in loads.iterator():
        available.add(load.pk)
        result = evaluate(ticket, load)
        state = MatchState.objects.filter(ticket=ticket, load_id_value=load.pk).first()
        if not result:
            if state and state.last_level:
                state.last_level = ""
                state.save(update_fields=["last_level"])
                Notification.objects.filter(ticket=ticket, snapshot__load_id=load.pk, kind__in=["match", "price"]).update(obsolete=True)
            continue
        if state is None:
            state = MatchState.objects.create(ticket=ticket, load_id_value=load.pk)
        if state.dismissed:
            continue
        price = f"{load.price_amount}:{load.currency}"
        improved = state.last_level != "full" and result["level"] == "full"
        first_or_returned = not state.last_level or not state.available
        price_improved = state.last_price != price and result["checks"]["price"] is True
        if first_or_returned or improved or price_improved:
            state.sequence += 1
            Notification.objects.filter(ticket=ticket, snapshot__load_id=load.pk, kind__in=["match", "price"]).update(obsolete=True)
            notify(ticket, "price" if state.last_price and price_improved else "match", f"match:{state.pk}:{state.sequence}", load, result)
        else:
            Notification.objects.filter(ticket=ticket, snapshot__load_id=load.pk, obsolete=False, kind__in=["match", "price"]).update(level=result["level"], reasons=result, snapshot=snapshot(load))
        state.last_level, state.last_price, state.available = result["level"], price, True
        state.save()
    for state in MatchState.objects.filter(ticket=ticket, available=True).exclude(load_id_value__in=available):
        old = Notification.objects.filter(ticket=ticket, snapshot__load_id=state.load_id_value).first()
        Notification.objects.filter(ticket=ticket, snapshot__load_id=state.load_id_value).update(obsolete=True)
        if old and not state.dismissed:
            state.sequence += 1
            notify(ticket, "unavailable", f"unavailable:{state.pk}:{state.sequence}", data=old.snapshot)
        state.available = False
        state.save(update_fields=["available", "sequence"])


def scan_all():
    for pk in Ticket.objects.exclude(status="closed").values_list("pk", flat=True).iterator():
        scan_ticket(pk)
    LinkToken.objects.filter(expires_at__lte=timezone.now()).delete()
