import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.http import Http404

from .locations import LocationError, parse_location
from .geocoding import reverse_place
from .models import MatchState, Notification, Preference, TelegramAccount, Ticket, Vehicle
from .serializers import PreferenceSerializer, TicketSerializer, VehicleSerializer
from .service import notify, scan_ticket


class BotError(Exception):
    def __init__(self, code, retry_after=60, description=""):
        self.code, self.retry_after = code, retry_after
        message = f"Telegram error {code}"
        if code == 409:
            if "webhook" in description.casefold():
                message += ": webhook is active; getUpdates polling cannot run with a webhook."
            else:
                message += ": another bot instance is polling this token. Keep one driver_bot running; use separate tokens for local and server environments."
        super().__init__(message)


def call(method, **payload):
    token = os.getenv("DRIVER_BOT_TOKEN", "")
    if not token:
        raise BotError("not_configured")
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except (ValueError, OSError):
            body = {}
        raise BotError(exc.code, body.get("parameters", {}).get("retry_after", 60), body.get("description", "")) from None
    except (OSError, ValueError):
        raise BotError("network") from None
    if not result.get("ok"):
        raise BotError(result.get("error_code", "unknown"), description=result.get("description", ""))
    return result["result"]


def delete_message(chat_id, message_id):
    if not message_id:
        return
    try:
        call("deleteMessage", chat_id=chat_id, message_id=message_id)
    except BotError as exc:
        if exc.code not in (400, 403):
            raise


def say(account, uz, ru=None, **kwargs):
    pref, _ = Preference.objects.get_or_create(owner=account.owner)
    markup = kwargs.pop("reply_markup", inline_keyboard(account, pref.language == "ru"))
    rows = []
    actions = {b["text"]: b["callback_data"] for row in menu_rows(pref.language == "ru") for b in row}
    ticket_flow = account.state.get("flow") == "ticket"
    for row in markup.get("inline_keyboard", []):
        buttons = []
        for button in row:
            if "callback_data" in button:
                buttons.append({"text": button["text"]})
                actions[button["text"]] = button["callback_data"]
        if buttons:
            rows.append(buttons)
    reply_markup = markup if ticket_flow else {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}
    result = call("sendMessage", chat_id=account.chat_id,
                  text=(ru if ru and pref.language == "ru" else uz)[:4000],
                  reply_markup=reply_markup, **kwargs)
    previous = account.ui.get("message_id")
    account.ui = {"message_id": result["message_id"], "actions": actions}
    account.save(update_fields=["ui"])
    if previous != result["message_id"]:
        delete_message(account.chat_id, previous)
    return result


TICKET_STEPS = ["title", "vehicle", "origins", "destinations"]
TICKET_FLOW_VERSION = 2
VEHICLE_STEPS = ["name", "kind", "capacity_tons", "volume_m3", "plate", "confirm"]
PREFERENCE_STEPS = ["language", "partial_interval_minutes", "quiet_start", "quiet_end", "timezone", "confirm"]
PROMPTS = {
    "title": ("🎫 Tiket nomini kiriting:", "🎫 Введите название заявки:"),
    "vehicle": ("🚛 Mashinani tanlang:", "🚛 Выберите машину:"),
    "origins": ("📍 Qayerdan yuk olasiz?\nTelegram lokatsiyasi yoki Google Maps / Yandex Maps havolasini yuboring. Shahar va manzil avtomatik aniqlanadi.", "📍 Откуда заберёте груз?\nОтправьте геопозицию Telegram или ссылку Google Maps / Яндекс Карт. Город и адрес определятся автоматически."),
    "destinations": ("🏁 Qayerga yuk olib bora olasiz?\nTelegram lokatsiyasi yoki Google Maps / Yandex Maps havolasini yuboring. Boradigan joy muhim bo‘lmasa, «🌍 Istalgan manzil»ni bosing.", "🏁 Куда можете отвезти груз?\nОтправьте геопозицию Telegram или ссылку Google Maps / Яндекс Карт. Если направление не важно, нажмите «🌍 Любое направление»."),
    "name": ("Mashina nomi? Masalan: Isuzu 01", "Название машины? Например: Isuzu 01"),
    "kind": ("Mashina turini tanlang.", "Выберите тип машины."),
    "capacity_tons": ("Maksimal sig‘im, tonna?", "Максимальная грузоподъёмность, тонн?"),
    "volume_m3": ("Hajmi m³ yoki -.", "Объём м³ или -."),
    "plate": ("Davlat raqami yoki -.", "Госномер или -."),
    "language": ("Til: uz / ru", "Язык: uz / ru"),
    "partial_interval_minutes": ("Qisman mos yuklar jamlanmasi: 0, 15, 30 yoki 60 daqiqa.", "Интервал подборки частичных совпадений: 0, 15, 30 или 60 минут."),
    "quiet_start": ("Tinch vaqt boshlanishi HH:MM yoki -.", "Начало тихих часов HH:MM или -."),
    "quiet_end": ("Tinch vaqt tugashi HH:MM yoki -.", "Конец тихих часов HH:MM или -."),
    "timezone": ("Vaqt zonasi: Asia/Tashkent yoki boshqa IANA zona.", "Часовой пояс: Asia/Tashkent или другая зона IANA."),
    "confirm": ("Ma’lumotlarni tekshiring va Saqlash tugmasini bosing.", "Проверьте данные и нажмите Сохранить."),
}


OPTION_LABELS = {
    "alternatives": ("Muqobil manzillar", "Альтернативные направления"),
    "ordered": ("Ketma-ket yo‘l", "Последовательный маршрут"),
    "anywhere": ("Istalgan manzil", "Любое направление"),
    "any_two": ("Istalgan 2 shart", "Любые 2 условия"),
    "route": ("Yo‘nalish va sig‘im shart", "Маршрут и грузоподъёмность обязательны"),
    "full": ("Faqat to‘liq mos", "Только полное совпадение"),
    "isothermal": ("Izotermik", "Изотермический"), "dump": ("Samosval", "Самосвал"),
    "lowbed": ("Tral", "Трал"), "container": ("Konteyner", "Контейнер"),
    "tent": ("Tent", "Тент"), "refrigerator": ("Refrijerator", "Рефрижератор"),
    "flatbed": ("Bort / platforma", "Борт / платформа"), "van": ("Furgon", "Фургон"),
    "tanker": ("Sisterna", "Цистерна"), "other": ("Boshqa", "Другой"),
    "trip": ("Butun reys", "За рейс"), "ton": ("Tonnasiga", "За тонну"),
    "ha": ("Ha", "Да"), "yoq": ("Yoq", "Нет"),
    "active": ("Faol", "Активна"), "paused": ("Pauzada", "На паузе"),
    "expired": ("Muddati tugagan", "Истекла"), "closed": ("Yopilgan", "Закрыта"),
}


def label(value, ru=False):
    return OPTION_LABELS.get(value, (value, value))[int(ru)]


def confirmation(account):
    data = account.state["data"]
    pref, _ = Preference.objects.get_or_create(owner=account.owner)
    ru = pref.language == "ru"
    lines = ["Проверьте данные:" if ru else "Ma’lumotlarni tekshiring:"]
    names = {"name": ("Mashina", "Машина"), "capacity_tons": ("Sig‘im (t)", "Грузоподъёмность (т)"), "volume_m3": ("Hajm (m³)", "Объём (м³)"), "plate": ("Davlat raqami", "Госномер"), "available_tons": ("Bo‘sh sig‘im (t)", "Свободная грузоподъёмность (т)"), "min_price": ("Eng kam narx", "Минимальная цена"), "currency": ("Valyuta", "Валюта"), "notes": ("Izoh", "Примечание"), "quiet_start": ("Tinch vaqt boshlanishi", "Начало тихих часов"), "quiet_end": ("Tinch vaqt tugashi", "Конец тихих часов"), "partial_interval_minutes": ("Jamlanma oralig‘i (daqiqa)", "Интервал подборки (минут)"), "timezone": ("Vaqt zonasi", "Часовой пояс"), "language": ("Til", "Язык")}
    for key, titles in names.items():
        if key in data:
            lines.append(f"{titles[int(ru)]}: {data[key] or '—'}")
    for key in ("route_mode", "price_basis", "match_mode", "kind"):
        if key in data:
            lines.append(label(data[key], ru))
    return "\n".join(lines)


def steps(state):
    return TICKET_STEPS if state["flow"] == "ticket" else VEHICLE_STEPS if state["flow"] == "vehicle" else PREFERENCE_STEPS


def public_keyboard():
    rows = []
    site = os.getenv("PUBLIC_SITE_URL", "").rstrip("/")
    if site.startswith("https://"):
        rows.append([{"text": "📝 Ro‘yxatdan o‘tish / Регистрация", "url": f"{site}/register"}])
        rows.append([{"text": "🌐 Sayt / Сайт", "url": site}])
    return {"inline_keyboard": rows}


def menu_rows(ru=False):
    return [
        [{"text": "🎫 Новая заявка" if ru else "🎫 Tiket ochish", "callback_data": "nav:ticket"}, {"text": "📋 Мои заявки" if ru else "📋 Tiketlarim", "callback_data": "nav:tickets"}],
        [{"text": "🚛 Мои машины" if ru else "🚛 Mashinalarim", "callback_data": "nav:vehicles"}, {"text": "⚙️ Настройки" if ru else "⚙️ Sozlamalar", "callback_data": "nav:settings"}],
    ]


def inline_keyboard(account, ru=False):
    state = account.state
    if not state:
        return {"inline_keyboard": menu_rows(ru)}
    if "ui_nonce" not in state:
        state["ui_nonce"] = secrets.token_hex(4)
        account.save(update_fields=["state"])
    nonce = state["ui_nonce"]
    key = steps(state)[state["index"]]
    def button(value, title=None):
        return {"text": title or label(value, ru), "callback_data": f"u:{nonce}:{value}"}
    rows = []
    if state["flow"] == "ticket":
        if key == "vehicle":
            rows += [[button(str(v.pk), f"🚛 {v.name} · {v.capacity_tons} t")] for v in Vehicle.objects.filter(owner=account.owner)]
            rows.append([{"text": "➕ Добавить машину" if ru else "➕ Mashina qo‘shish", "callback_data": "nav:vehicle"}])
        elif key in ("origins", "destinations"):
            places = state["data"].get(key, [])
            if places:
                if len(places) < 10:
                    rows.append([button("add_place", "➕ Добавить адрес" if ru else "➕ Manzil qo‘shish")])
                if key == "origins":
                    done_label = "✅ Далее" if ru else "✅ Davom etish"
                elif state.get("instance"):
                    done_label = "✅ Сохранить заявку" if ru else "✅ Tiketni saqlash"
                else:
                    done_label = "✅ Создать заявку" if ru else "✅ Tiketni ochish"
                rows.append([button("done", done_label)])
            if key == "destinations":
                rows.append([button("anywhere", "🌍 Любое направление" if ru else "🌍 Istalgan manzil")])
        rows.append([button("/back", "⬅️ Назад" if ru else "⬅️ Orqaga"), button("/cancel", "✖️ Отмена" if ru else "✖️ Bekor qilish")])
        return {"inline_keyboard": rows}
    choices = {"kind": ["tent", "van", "refrigerator", "isothermal", "flatbed", "tanker", "dump", "lowbed", "container", "other"], "partial_interval_minutes": ["0", "15", "30", "60"], "language": ["uz", "ru"]}
    if key == "confirm":
        rows.append([button("ha", "✅ Сохранить" if ru else "✅ Saqlash")])
    elif key in choices:
        values = choices[key]
        rows += [[button(v) for v in values[i:i+2]] for i in range(0, len(values), 2)]
    if key in ("volume_m3", "plate", "quiet_start", "quiet_end"):
        rows.append([button("-", "⏭ Пропустить" if ru else "⏭ O‘tkazib yuborish")])
    rows.append([button("/back", "⬅️ Назад" if ru else "⬅️ Orqaga"), button("/cancel", "✖️ Отмена" if ru else "✖️ Bekor qilish")])
    rows.append([{"text": "🏠 Меню" if ru else "🏠 Menyu", "callback_data": "nav:menu"}])
    return {"inline_keyboard": rows}


def prompt(account):
    state = account.state
    key = steps(state)[state["index"]]
    uz, ru = PROMPTS[key]
    pref, _ = Preference.objects.get_or_create(owner=account.owner)
    state["ui_nonce"] = secrets.token_hex(4)
    account.save(update_fields=["state"])
    kwargs = {}
    if state["flow"] == "ticket":
        if key in ("origins", "destinations"):
            places = state["data"].get(key, [])
            if places:
                names = "\n".join(f"{i}. {p['name']}" + (f" — {p['address'][:140]}" if p.get("address") else "") for i, p in enumerate(places, 1))
                uz = f"{'📍 Yuk olish manzillari' if key == 'origins' else '🏁 Yuk olib borish manzillari'}:\n{names}\n\n"
                ru = f"{'📍 Адреса погрузки' if key == 'origins' else '🏁 Адреса назначения'}:\n{names}\n\n"
                if state.get("adding_place"):
                    uz += "Yana bir lokatsiya yoki xarita havolasini yuboring."
                    ru += "Отправьте ещё одну геопозицию или ссылку на карту."
                else:
                    uz += "Yana manzil qo‘shing yoki " + ("davom eting." if key == "origins" else "tiketni saqlang. Mos yuklar saytga va shu botga keladi.")
                    ru += "Добавьте адрес или " + ("продолжите." if key == "origins" else "сохраните заявку. Подходящие грузы появятся на сайте и в этом боте.")
                if any(p.get("geocoded") for p in places):
                    uz += "\n© OpenStreetMap contributors — https://www.openstreetmap.org/copyright"
                    ru += "\n© OpenStreetMap contributors — https://www.openstreetmap.org/copyright"
        if key == "vehicle" and not Vehicle.objects.filter(owner=account.owner).exists():
            uz, ru = "Avval mashina qo‘shing. Keyin tiket ochishni shu joydan davom ettirasiz.", "Сначала добавьте машину. Затем продолжим создание заявки с этого шага."
        return say(account, uz, ru, link_preview_options={"is_disabled": True})
    if key == "confirm":
        summary = confirmation(account)
        return say(account, summary + "\n\n" + (ru if pref.language == "ru" else uz))
    return say(account, uz, ru, **kwargs)


def parse_answer(key, text, message, data, state=None):
    if key == "kind":
        for value, labels in OPTION_LABELS.items():
            if text in labels:
                text = value
                break
    def number(value):
        result = Decimal(value)
        if not result.is_finite() or result < 0:
            raise ValueError()
        return str(result)
    if key == "partial_interval_minutes":
        data[key] = int(text)
    elif key in ("capacity_tons", "volume_m3"):
        data[key] = None if key == "volume_m3" and text == "-" else number(text)
    elif key in ("quiet_start", "quiet_end"):
        data[key] = None if text == "-" else datetime.strptime(text, "%H:%M").time().isoformat()
    else:
        choices = {"kind": ['tent', 'van', 'refrigerator', 'isothermal', 'flatbed', 'tanker', 'dump', 'lowbed', 'container', 'other'], "currency": ["UZS", "USD"], "price_basis": ["trip", "ton"], "match_mode": ["any_two", "route", "full"], "route_mode": ["alternatives", "ordered", "anywhere"], "language": ["uz", "ru"]}
        if key in choices and text not in choices[key]:
            raise ValueError()
        data[key] = "" if text == "-" else text


def ticket_state():
    return {"flow": "ticket", "version": TICKET_FLOW_VERSION, "index": 0, "data": {}}


def save_ticket(account):
    state = account.state
    data = state["data"]
    vehicle = Vehicle.objects.filter(pk=data.get("vehicle"), owner=account.owner).first()
    if vehicle is None:
        raise ValidationError("O‘zingizga tegishli mashinani tanlang.")
    now = timezone.now()
    # Every hidden search option has a predictable default in the short bot flow.
    fields = ("name", "lat", "lon", "source_url", "address", "geocoded")
    places = {key: [{k: v for k, v in p.items() if k in fields} for p in data.get(key, [])] for key in ("origins", "destinations")}
    payload = {
        "title": data.get("title", ""), "vehicle": vehicle.pk, **places,
        "route_mode": "anywhere" if data.get("route_mode") == "anywhere" else "alternatives",
        "current_location": places["origins"][0] if places["origins"] else {},
        "ready_at": now.isoformat(), "expires_at": (now + timedelta(days=7)).isoformat(),
        "available_tons": str(vehicle.capacity_tons), "status": "active", "waypoints": [],
        "partial_load": False, "min_price": "0", "currency": "UZS", "price_basis": "trip",
        "match_mode": "route", "notes": "",
    }
    with transaction.atomic():
        instance = Ticket.objects.filter(pk=state.get("instance"), owner=account.owner).first()
        if state.get("instance") and instance is None:
            raise ValidationError("Tiket topilmadi.")
        if instance is None and Ticket.objects.filter(owner=account.owner, status__in=["active", "paused"]).count() >= 20:
            raise ValidationError("At most 20 active or paused tickets.")
        serializer = TicketSerializer(instance, data=payload, context={"request": SimpleNamespace(user=account.owner)})
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save(owner=account.owner)
        if instance is None:
            notify(ticket, "ticket_created", f"ticket:{ticket.pk}")
        scan_ticket(ticket.pk)
        account.state = {}
        account.save(update_fields=["state"])
    return say(account, f"✅ #{ticket.pk} — {ticket.title}\nTiket saytda ham, botda ham saqlandi. Mos yuklar haqida shu botda va saytda xabar olasiz. Qidiruv 7 kun faol.", f"✅ #{ticket.pk} — {ticket.title}\nЗаявка сохранена на сайте и в боте. Уведомления о подходящих грузах придут сюда и на сайт. Поиск активен 7 дней.")


def ticket_answer(account, key, text, message):
    state, data = account.state, account.state["data"]
    if key == "title":
        if not text or len(text) > 120:
            raise ValidationError("Tiket nomi 1–120 belgidan iborat bo‘lsin.")
        data["title"] = text
    elif key == "vehicle":
        if not text.isdigit() or not Vehicle.objects.filter(pk=int(text), owner=account.owner).exists():
            raise ValidationError("O‘zingizga tegishli mashinani tanlang.")
        data["vehicle"] = int(text)
    else:
        if key == "destinations" and text == "anywhere":
            data.update(destinations=[], route_mode="anywhere")
            return save_ticket(account)
        if text in ("done", "Tayyor", "Готово"):
            if not data.get(key):
                raise LocationError("empty")
            state.pop("adding_place", None)
            if key == "destinations":
                data["route_mode"] = "alternatives"
                return save_ticket(account)
        elif text == "add_place":
            state["adding_place"] = True
            account.save(update_fields=["state"])
            return prompt(account)
        else:
            places = data.get(key, [])
            if len(places) >= 10:
                raise LocationError("limit")
            place = parse_location(text, message)
            if place.get("lat") is None:
                raise LocationError("pin")
            place.update(reverse_place(place["lat"], place["lon"]))
            if not any(p.get("lat") == place["lat"] and p.get("lon") == place["lon"] for p in places):
                data[key] = places + [place]
            state.pop("adding_place", None)
            account.save(update_fields=["state"])
            return prompt(account)
    state["index"] += 1
    account.save(update_fields=["state"])
    return prompt(account)


def callback(account, query):
    if query.get("id"):
        call("answerCallbackQuery", callback_query_id=query["id"])
    parts = query.get("data", "").split(":")
    if len(parts) != 2 or not parts[1].isdigit():
        return
    action, pk = parts[0], int(parts[1])
    if action in ("pause", "resume", "close", "extend"):
        ticket = Ticket.objects.filter(pk=pk, owner=account.owner).first()
        if ticket is None:
            return
        if action == "extend":
            ticket.expires_at = timezone.now() + timedelta(days=7)
            ticket.status = "active"
        else:
            ticket.status = {"pause": "paused", "resume": "active", "close": "closed"}[action]
            if ticket.status == "active" and ticket.expires_at <= timezone.now():
                return say(account, "Avval tiketni uzaytiring.", "Сначала продлите заявку.")
        ticket.save()
        scan_ticket(ticket.pk)
        say(account, f"#{ticket.pk}: {ticket.status}")
    elif action in ("dismiss", "phone"):
        note = Notification.objects.filter(pk=pk, owner=account.owner).first()
        if not note:
            return
        if action == "phone":
            entry = getattr(note.load, "telegram_entry", None) if note.load_id else None
            if note.obsolete or not note.load_id or note.load.status != "open" or (entry and entry.expires_at and entry.expires_at <= timezone.now()):
                say(account, "Yuk endi mavjud emas.", "Груз больше недоступен.")
            else:
                say(account, note.load.contact_phone or "—")
        else:
            MatchState.objects.filter(ticket=note.ticket, load_id_value=note.snapshot.get("load_id")).update(dismissed=True)
            Notification.objects.filter(ticket=note.ticket, snapshot__load_id=note.snapshot.get("load_id")).update(obsolete=True, read_at=timezone.now())
            say(account, "Bu yuk uchun xabarlar o‘chirildi.", "Уведомления об этом грузе отключены.")


def handle_update(update):
    query = update.get("callback_query")
    message = query.get("message", {}) if query else update.get("message", {})
    if message.get("chat", {}).get("type") != "private":
        return
    chat_id = message["chat"]["id"]
    sender = (query or message).get("from", {}).get("id")
    if sender != chat_id:
        return
    reset_handled = False
    if not query:
        # Reset endpoints lock the challenge before the Telegram account, too.
        from authentication.password_reset import handle_password_reset_message
        reset_handled = handle_password_reset_message(message, call, delete_message)
    TelegramAccount.objects.filter(chat_id=chat_id, blocked=True, owner__is_active=True).update(blocked=False)
    if reset_handled:
        return
    if not query:
        from authentication.telegram_verification import handle_registration_message
        if handle_registration_message(message, call, delete_message):
            return
    text = message.get("text", "").strip()[:4000]
    if not query and text.startswith("/start "):
        text = "/start"
    account = TelegramAccount.objects.select_related("owner").filter(chat_id=chat_id, owner__is_active=True).first()
    if not account:
        if query:
            call("answerCallbackQuery", callback_query_id=query["id"])
        call("sendMessage", chat_id=chat_id, text="YukFlow saytida ro‘yxatdan o‘ting va telefoningizni shu bot orqali tasdiqlang. Akkaunt avtomatik ulanadi. / Зарегистрируйтесь на сайте YukFlow и подтвердите номер в этом боте. Аккаунт подключится автоматически.", reply_markup=public_keyboard())
        return
    if account.owner.role != "driver":
        if query and query.get("id"):
            call("answerCallbackQuery", callback_query_id=query["id"])
        result = call("sendMessage", chat_id=chat_id, text="Telegram akkauntingiz YukFlow’ga ulangan. Yuk joylash uchun saytdagi kabinetingizga kiring. / Telegram подключён к YukFlow. Размещайте грузы в личном кабинете на сайте.", reply_markup={"remove_keyboard": True})
        delete_message(chat_id, account.ui.get("message_id"))
        delete_message(chat_id, message.get("message_id"))
        account.ui = {"message_id": result["message_id"], "actions": {}}
        account.save(update_fields=["ui"])
        return
    if account.state.get("flow") == "ticket" and account.state.get("version") != TICKET_FLOW_VERSION:
        account.state = ticket_state()
        account.save(update_fields=["state"])
        if query and query.get("id"):
            call("answerCallbackQuery", callback_query_id=query["id"])
        return prompt(account)
    if not query:
        delete_message(chat_id, message.get("message_id"))
        payload = None if update.get("_resolved") else account.ui.get("actions", {}).get(text)
        if payload:
            return handle_update({"callback_query": {
                "from": {"id": sender}, "data": payload, "message": message,
            }})
    if query:
        payload = query.get("data", "")
        if not payload.startswith(("nav:", "u:")):
            return callback(account, query)
        if query.get("id"):
            call("answerCallbackQuery", callback_query_id=query["id"])
        parts = payload.split(":", 2)
        if parts[0] == "nav":
            commands = {"ticket": "/ticket", "vehicle": "/vehicle", "tickets": "/tickets", "settings": "/settings", "menu": "/start", "vehicles": "/vehicles"}
            if len(parts) == 2:
                text = commands.get(parts[1])
            elif len(parts) == 3 and parts[1] in ("edit", "return") and parts[2].isdigit():
                text = f"/{parts[1]} {parts[2]}"
            else:
                return
            if not text:
                return
        else:
            if len(parts) != 3 or not account.state or parts[1] != account.state.get("ui_nonce"):
                return say(account, "Bu eski tugma. Oxirgi xabardagi tugmalardan foydalaning.", "Эта кнопка устарела. Используйте кнопки последнего сообщения.")
            pref, _ = Preference.objects.get_or_create(owner=account.owner)
            allowed = {button.get("callback_data") for row in inline_keyboard(account, pref.language == "ru")["inline_keyboard"] for button in row}
            if payload not in allowed:
                return
            text = parts[2]
            if text == "location":
                return say(account, "📍 Skrepka → Lokatsiya → xaritada kerakli joyni tanlang va yuboring. Hozirgi joyingizni ham shu yerdan yuborasiz.", "📍 Скрепка → Геопозиция → выберите нужную точку и отправьте. Текущее место отправляется там же.")
            if text == "maps":
                return say(account, "🗺 Google Maps yoki Yandex Maps’da nuqtani tanlang → Ulashish → havolani shu chatga yuboring.", "🗺 Выберите точку в Google Maps или Яндекс Картах → Поделиться → отправьте ссылку в этот чат.")
        return handle_update({"_resolved": True, "message": {"chat": message["chat"], "from": {"id": sender}, "text": text}})
    if text in ("/cancel", "/start", "/help"):
        account.state = {}
        account.save(update_fields=["state"])
        return say(account, "Kerakli bo‘limni tanlang.", "Выберите раздел.")
    if text == "/vehicles":
        vehicles = list(Vehicle.objects.filter(owner=account.owner))
        pref, _ = Preference.objects.get_or_create(owner=account.owner)
        ru = pref.language == "ru"
        lines = [f"🚛 {v.name} · {label(v.kind, ru)} · {v.capacity_tons} t" for v in vehicles]
        rows = [[{"text": "➕ Добавить машину" if ru else "➕ Mashina qo‘shish", "callback_data": "nav:vehicle"}]] + menu_rows(ru)
        return say(account, "\n".join(lines) or "Hali mashina qo‘shilmagan.", "\n".join(lines) or "Машины пока не добавлены.", reply_markup={"inline_keyboard": rows})
    if text == "/tickets":
        pref, _ = Preference.objects.get_or_create(owner=account.owner)
        ru = pref.language == "ru"
        lines, rows = [], []
        for ticket in Ticket.objects.filter(owner=account.owner)[:20]:
            lines.append(f"#{ticket.pk} {ticket.title} · {label(ticket.status, ru)}")
            actions = [("pause", "Pauza", "Пауза"), ("resume", "Davom", "Продолжить"),
                       ("extend", "+7 kun", "+7 дней"), ("close", "Yopish", "Закрыть"),
                       ("nav:edit", "Tahrirlash", "Изменить"), ("nav:return", "Qaytish", "Обратно")]
            buttons = [{"text": f"#{ticket.pk} {r if ru else u}", "callback_data": f"{action}:{ticket.pk}"}
                       for action, u, r in actions]
            rows.extend([buttons[i:i+2] for i in range(0, len(buttons), 2)])
        rows += menu_rows(ru)
        return say(account, "\n".join(lines) or ("Заявок пока нет." if ru else "Hali tiket yo‘q."),
                   reply_markup={"inline_keyboard": rows})
    if text in ("/ticket", "/vehicle", "/settings") or text.startswith("/edit "):
        flow = "vehicle" if text == "/vehicle" else "preferences" if text == "/settings" else "ticket"
        state = ticket_state() if flow == "ticket" else {"flow": flow, "index": 0, "data": {}}
        if flow == "vehicle" and account.state.get("flow") == "ticket":
            state["resume_ticket"] = account.state
        if text.startswith("/edit "):
            try:
                ticket = Ticket.objects.get(pk=int(text.split()[1]), owner=account.owner)
                state.update(instance=ticket.pk, data=dict(TicketSerializer(ticket).data))
            except (ValueError, IndexError, Ticket.DoesNotExist):
                return say(account, "Tiket topilmadi.", "Заявка не найдена.")
        account.state = state
        account.save(update_fields=["state"])
        return prompt(account)
    if text.startswith("/return "):
        try:
            from .views import TicketViewSet
            ticket_id = int(text.split()[1])
            view = TicketViewSet()
            request = SimpleNamespace(user=account.owner, data={})
            view.request, view.format_kwarg, view.kwargs = request, None, {"pk": ticket_id}
            view.return_trip(request, str(ticket_id))
            return say(account, "Qaytish tiketi pauzada yaratildi. /tickets", "Обратная заявка создана на паузе. /tickets")
        except (ValueError, ValidationError, Http404):
            return say(account, "Tiketni va manzillarni tekshiring.", "Проверьте заявку и направления.")
    if not account.state:
        return say(account, "Kerakli bo‘limni tanlang.")
    state = account.state
    if text == "/back":
        state.pop("adding_place", None)
        state["index"] = max(0, state["index"] - 1)
        account.save(update_fields=["state"])
        return prompt(account)
    key = steps(state)[state["index"]]
    try:
        if state["flow"] == "ticket":
            return ticket_answer(account, key, text, message)
        if key == "confirm":
            if text.casefold() not in ("ha", "да"):
                return prompt(account)
            if state["flow"] == "vehicle":
                serializer = VehicleSerializer(data=state["data"])
            else:
                pref, _ = Preference.objects.get_or_create(owner=account.owner)
                serializer = PreferenceSerializer(pref, data=state["data"], partial=True)
            serializer.is_valid(raise_exception=True)
            obj = serializer.save(owner=account.owner)
            if isinstance(obj, Vehicle) and state.get("resume_ticket"):
                account.state = state["resume_ticket"]
                account.state["data"]["vehicle"] = obj.pk
                account.state["index"] = TICKET_STEPS.index("origins")
                account.save(update_fields=["state"])
                return prompt(account)
            account.state = {}
            account.save(update_fields=["state"])
            return say(account, "✅ Saqlandi. Kerakli bo‘limni tanlang.", "✅ Сохранено. Выберите раздел.")
        if text != "." or not state.get("instance"):
            if parse_answer(key, text, message, state["data"], state) is False:
                account.save(update_fields=["state"])
                return prompt(account)
        state["index"] += 1
        account.save(update_fields=["state"])
        prompt(account)
    except LocationError as exc:
        errors = {
            "geocoding": ("Bu nuqtaning shahar/manzilini avtomatik aniqlab bo‘lmadi. Lokatsiya yoki aniq Google Maps / Yandex Maps havolasini qayta yuboring.", "Не удалось автоматически определить город и адрес точки. Повторно отправьте геопозицию или ссылку на точку Google Maps / Яндекс Карт."),
            "network": ("Xarita havolasini ochib bo‘lmadi. Qayta yuboring yoki Telegram lokatsiyasini yuboring.", "Не удалось открыть ссылку. Повторите или отправьте геопозицию Telegram."),
            "name": ("Telegram lokatsiyasi yoki xarita havolasini yuboring.", "Отправьте геопозицию Telegram или ссылку на карту."),
            "empty": ("Avval kamida bitta joy yuboring.", "Сначала отправьте хотя бы одну точку."),
            "limit": ("Ko‘pi bilan 10 ta manzil qo‘shish mumkin. Davom etish yoki Tiketni ochish tugmasini bosing.", "Можно добавить до 10 точек. Нажмите Готово."),
        }
        uz, ru = errors.get(str(exc), ("Google Maps yoki Yandex Maps’da aniq nuqtani tanlab Ulashish havolasini yuboring. Yoki Telegram lokatsiyasini yuboring.", "Выберите точку в Google Maps или Яндекс Картах и отправьте ссылку Поделиться. Или отправьте геопозицию Telegram."))
        say(account, uz, ru)
    except (ValueError, TypeError, InvalidOperation, ValidationError) as exc:
        detail = str(exc.detail)[:600] if isinstance(exc, ValidationError) else ""
        say(account, f"Qiymatni tekshiring. /back bilan qaytishingiz mumkin. {detail}", f"Проверьте значение. Можно вернуться: /back. {detail}")
