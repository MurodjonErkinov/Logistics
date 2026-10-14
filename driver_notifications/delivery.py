from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import Notification, Preference, TelegramAccount
from .telegram import BotError, call

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
            rows.append([{"text": "+7 kun / дней", "callback_data": f"extend:{note.ticket_id}"}, {"text": "Yopish / Закрыть", "callback_data": f"close:{note.ticket_id}"}])
        elif note.kind == "ticket_created":
            rows.append([{"text": "Tiket / Заявка", "url": f"{site}/driver/tickets"}])
        elif not note.obsolete and note.kind != "unavailable":
            rows.append([{"text": f"#{note.snapshot.get('load_id')} Yuk / Груз", "url": f"{site}/loads/{note.snapshot.get('load_id')}"}, {"text": "📞", "callback_data": f"phone:{note.pk}"}])
            rows.append([{"text": "Mos emas / Не подходит", "callback_data": f"dismiss:{note.pk}"}, {"text": "Pauza / Пауза", "callback_data": f"pause:{note.ticket_id}"}])
    rows.append([{"text": "🏠 Menyu / Меню", "callback_data": "nav:menu"}, {"text": "📋 Tiketlar / Заявки", "callback_data": "nav:tickets"}])
    rows.append([{"text": "Sayt / Сайт", "url": f"{site}/notifications"}])
    return {"inline_keyboard": rows}


def deliver():
    now = timezone.now()
    for account in TelegramAccount.objects.filter(blocked=False, owner__role="driver", owner__is_active=True).select_related("owner"):
        pref, _ = Preference.objects.get_or_create(owner=account.owner)
        if not pref.telegram_enabled or quiet(pref, now):
            continue
        pending = Notification.objects.filter(owner=account.owner, sent_at=None, obsolete=False, deliver_after__lte=now).select_related("ticket").order_by("created_at")
        pending = pending.exclude(kind__in=["match", "price"], ticket__status__in=["paused", "closed", "expired"])
        first = pending.first()
        if first is None:
            continue
        notes = [first]
        if first.level == "partial" and pref.partial_interval_minutes:
            notes = list(Notification.objects.filter(owner=account.owner, sent_at=None, obsolete=False, level="partial", attempts=0, ticket__status="active").select_related("ticket").order_by("created_at")[:5]) or [first]
        try:
            text = "\n\n".join(render(note, pref.language) for note in notes)
            result = call("sendMessage", chat_id=account.chat_id, text=text[:4000], reply_markup=keyboard(notes), link_preview_options={"is_disabled": True})
            Notification.objects.filter(pk__in=[n.pk for n in notes]).update(sent_at=now, message_id=result["message_id"], message_chat_id=account.chat_id, delivery_error="")
            for note in notes:
                if note.kind == "unavailable":
                    old = Notification.objects.filter(owner=account.owner, snapshot__load_id=note.snapshot.get("load_id"), message_chat_id=account.chat_id, obsolete=True).exclude(message_id=None)
                    for message_id in old.values_list("message_id", flat=True).distinct():
                        group = list(Notification.objects.filter(message_id=message_id, message_chat_id=account.chat_id).select_related("ticket"))
                        try:
                            call("editMessageText", chat_id=account.chat_id, message_id=message_id, text="\n\n".join(render(n, pref.language) for n in group)[:4000], reply_markup=keyboard(group))
                        except BotError:
                            pass
        except BotError as exc:
            for note in notes:
                note.attempts += 1
                note.delivery_error = str(exc)
                note.deliver_after = now + timedelta(seconds=max(exc.retry_after, min(3600, 30 * 2 ** min(note.attempts, 7))))
                note.save(update_fields=["attempts", "delivery_error", "deliver_after"])
            if exc.code == 403:
                account.blocked = True
                account.save(update_fields=["blocked"])
