from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import Notification, Preference, TelegramAccount
from .telegram import BotError, call, send_ui

LABELS = {"uz": {"route": "Yo‘nalish", "vehicle": "Mashina turi", "capacity": "Sig‘im", "time": "Vaqt", "price": "Narx"}, "ru": {"route": "Маршрут", "vehicle": "Тип машины", "capacity": "Грузоподъёмность", "time": "Время", "price": "Цена"}}


def quiet(pref, now):
    if not pref.quiet_start or not pref.quiet_end:
        return False
    local = now.astimezone(ZoneInfo(pref.timezone)).time().replace(tzinfo=None)
    if pref.quiet_start < pref.quiet_end:
        return pref.quiet_start <= local < pref.quiet_end
    return local >= pref.quiet_start or local < pref.quiet_end


def render(note, language):
    ru = language == "ru"
    if note.kind == "ticket_created":
        return f"🎫 #{note.ticket_id} {note.ticket.title}\n" + ("Заявка создана. Управление: /tickets" if ru else "Tiket yaratildi. Boshqarish: /tickets")
    if note.kind in ("expired", "expiring"):
        return f"⏰ #{note.ticket_id} {note.ticket.title}\n" + (("Срок заявки истёк" if note.kind == "expired" else "Срок заявки скоро истечёт") if ru else ("Tiket muddati tugadi" if note.kind == "expired" else "Tiket muddati tugayapti"))
    data = note.snapshot
    title = ("Груз недоступен" if ru else "Yuk mavjud emas") if note.kind == "unavailable" or note.obsolete else ("Полное совпадение" if ru else "To‘liq mos") if note.level == "full" else ("Частичное совпадение" if ru else "Qisman mos")
    checks = " · ".join(f"{'✅' if value is True else '❌' if value is False else '❔'} {LABELS[language][key]}" for key, value in note.reasons.get("checks", {}).items())
    return f"📦 {title} · #{note.ticket_id}\n{data.get('origin', '')} → {data.get('destination', '')}\n{data.get('cargo_name', '')} · {data.get('weight_tons', '')} t\n{data.get('price') or ('Договорная' if ru else 'Kelishiladi')} {data.get('currency', '')}{' / t' if data.get('price_basis') == 'ton' else ''}\n{checks}\n" + ("Доступность уточните у отправителя." if ru else "Yuk bo‘shligini egasidan aniqlang.")


def keyboard(notes):
    import os
    site = os.getenv("PUBLIC_SITE_URL", "http://localhost:3018").rstrip("/")
    rows = []
    for note in notes:
        if note.kind in ("expired", "expiring"):
            rows.append([{"text": f"#{note.ticket_id} +7 kun / дней", "callback_data": f"extend:{note.ticket_id}"}, {"text": f"#{note.ticket_id} Yopish / Закрыть", "callback_data": f"close:{note.ticket_id}"}])
        elif note.kind == "ticket_created":
            rows.append([{"text": "Tiket / Заявка", "url": f"{site}/driver/tickets"}])
        elif not note.obsolete and note.kind != "unavailable":
            rows.append([{"text": f"#{note.snapshot.get('load_id')} Yuk / Груз", "url": f"{site}/loads/{note.snapshot.get('load_id')}"}, {"text": f"📞 #{note.snapshot.get('load_id')}", "callback_data": f"phone:{note.pk}"}])
            rows.append([{"text": f"#{note.snapshot.get('load_id')} Mos emas / Не подходит", "callback_data": f"dismiss:{note.pk}"}, {"text": f"#{note.ticket_id} Pauza / Пауза", "callback_data": f"pause:{note.ticket_id}"}])
    rows.append([{"text": "🏠 Menyu / Меню", "callback_data": "nav:menu"}, {"text": "📋 Tiketlar / Заявки", "callback_data": "nav:tickets"}])
    rows.append([{"text": "Sayt / Сайт", "url": f"{site}/notifications"}])
    return {"inline_keyboard": rows}


def deliver():
    now = timezone.now()
    accounts = TelegramAccount.objects.filter(blocked=False, owner__role="driver", owner__is_active=True)
    for account_id in accounts.values_list("pk", flat=True).iterator():
        deliver_account(account_id, now)


@transaction.atomic
def deliver_account(account_id, now):
    account = TelegramAccount.objects.select_for_update(of=("self",)).select_related("owner").filter(pk=account_id, blocked=False, owner__role="driver", owner__is_active=True).first()
    # Keep the driver's current question/keyboard visible until the wizard ends.
    if account is None or account.state:
        return
    pref, _ = Preference.objects.get_or_create(owner=account.owner)
    if not pref.telegram_enabled or quiet(pref, now):
        return
    pending = Notification.objects.filter(owner=account.owner, sent_at=None, obsolete=False, deliver_after__lte=now).select_related("ticket").order_by("created_at")
    pending = pending.exclude(kind__in=["match", "price"], ticket__status__in=["paused", "closed", "expired"])
    first = pending.first()
    if first is None:
        return
    notes = [first]
    if first.level == "partial" and pref.partial_interval_minutes:
        notes = list(pending.filter(level="partial", attempts=0, ticket__status="active")[:5]) or [first]
    try:
        text = "\n\n".join(render(note, pref.language) for note in notes)
        result = send_ui(account, text, keyboard(notes), send=call, link_preview_options={"is_disabled": True})
        Notification.objects.filter(pk__in=[n.pk for n in notes]).update(sent_at=now, message_id=result["message_id"], message_chat_id=account.chat_id, delivery_error="")
    except BotError as exc:
        for note in notes:
            note.attempts += 1
            note.delivery_error = str(exc)
            note.deliver_after = now + timedelta(seconds=max(exc.retry_after, min(3600, 30 * 2 ** min(note.attempts, 7))))
            note.save(update_fields=["attempts", "delivery_error", "deliver_after"])
        if exc.code == 403:
            account.blocked = True
            account.save(update_fields=["blocked"])
