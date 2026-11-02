"""Durable, ticket-scoped cleanup of delivered Telegram notifications."""

from django.db import transaction

from .models import Notification, Preference, TelegramAccount


@transaction.atomic
def queue_ticket_cleanup(ticket_id, owner_id):
    account = TelegramAccount.objects.select_for_update().filter(owner_id=owner_id).first()
    notes = Notification.objects.filter(ticket_id=ticket_id, owner_id=owner_id)
    if account:
        jobs = account.ui.setdefault("notification_cleanup", {})
        messages = notes.filter(message_chat_id=account.chat_id).exclude(message_id=None).order_by().values_list("message_id", flat=True).distinct()
        for message_id in messages:
            key = str(message_id)
            jobs[key] = sorted(set(jobs.get(key, [])) | {ticket_id})
        account.save(update_fields=["ui"])
    notes.update(obsolete=True)


def queue_closed_ticket_cleanup(account):
    # Persisted closed status is also the retry source after a worker restart.
    notes = Notification.objects.filter(owner=account.owner, ticket__status="closed")
    ticket_ids = list(notes.exclude(message_id=None).order_by().values_list("ticket_id", flat=True).distinct())
    for ticket_id in ticket_ids:
        queue_ticket_cleanup(ticket_id, account.owner_id)
    notes.filter(obsolete=False).update(obsolete=True)


@transaction.atomic
def process_ticket_cleanup(account, send=None):
    from .delivery import render
    from .telegram import BotError, call, menu_rows, send_ui

    send = send or call
    locked = TelegramAccount.objects.select_for_update().get(pk=account.pk)
    jobs = locked.ui.get("notification_cleanup", {})
    if not jobs:
        account.ui = locked.ui
        return
    pref, _ = Preference.objects.get_or_create(owner=locked.owner)
    refresh_menu = False
    for key, ticket_ids in list(jobs.items())[:100]:
        message_id = int(key)
        group = Notification.objects.filter(owner=locked.owner, message_chat_id=locked.chat_id, message_id=message_id)
        survivors = list(group.exclude(ticket_id__in=ticket_ids).exclude(ticket__status="closed").select_related("ticket").order_by("created_at"))
        try:
            if survivors:
                # Old digests may contain several tickets: retain the other tickets.
                send("editMessageText", chat_id=locked.chat_id, message_id=message_id,
                     text="\n\n".join(render(note, pref.language) for note in survivors)[:4000],
                     reply_markup={"inline_keyboard": []})
            else:
                send("deleteMessage", chat_id=locked.chat_id, message_id=message_id)
        except BotError as exc:
            if exc.code not in (400, 403):
                break  # Keep the job for the next worker pass, including after deletion.
        group.filter(ticket_id__in=ticket_ids).update(message_id=None, message_chat_id=None)
        was_current = message_id in (locked.ui.get("notification_message_id"), locked.ui.get("message_id"))
        if locked.ui.get("notification_message_id") == message_id and not survivors:
            locked.ui.pop("notification_message_id", None)
        if locked.ui.get("message_id") == message_id:
            locked.ui["message_id"] = None
        if was_current and locked.ui.get("message_id") is None and not locked.state:
            refresh_menu = True
        jobs.pop(key)
    locked.ui["notification_cleanup"] = jobs
    locked.save(update_fields=["ui"])
    if refresh_menu:
        send_ui(locked, "Tiket bo‘yicha bildirishnomalar tozalandi." if pref.language != "ru" else "Уведомления по заявке удалены.",
                {"inline_keyboard": menu_rows(pref.language == "ru")}, send=send)
    account.ui = locked.ui
