import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.http import Http404

from .locations import LocationError, parse_location
from .models import MatchState, Notification, Preference, TelegramAccount, Ticket, Vehicle
from .serializers import PreferenceSerializer, TicketSerializer, VehicleSerializer
from .service import bind_account, notify, scan_ticket


class BotError(Exception):
    def __init__(self, code, retry_after=60):
        self.code, self.retry_after = code, retry_after
        super().__init__(f"Telegram error {code}")


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
        raise BotError(exc.code, body.get("parameters", {}).get("retry_after", 60)) from None
    except (OSError, ValueError):
        raise BotError("network") from None
    if not result.get("ok"):
        raise BotError(result.get("error_code", "unknown"))
    return result["result"]


def say(account, uz, ru=None, **kwargs):
    pref, _ = Preference.objects.get_or_create(owner=account.owner)
    kwargs.setdefault("reply_markup", inline_keyboard(account, pref.language == "ru"))
    return call("sendMessage", chat_id=account.chat_id, text=(ru if ru and pref.language == "ru" else uz)[:4000], **kwargs)


TICKET_STEPS = ["title", "vehicle", "current_location", "origins", "origin_points", "origin_radius", "route_mode", "destinations", "destination_points", "prices", "etas", "priorities", "radii", "ready_at", "expires_at", "available_tons", "partial_load", "currency", "price_basis", "min_price", "match_mode", "waypoints", "notes", "confirm"]
VEHICLE_STEPS = ["name", "kind", "capacity_tons", "volume_m3", "plate", "confirm"]
PREFERENCE_STEPS = ["language", "telegram_enabled", "partial_interval_minutes", "quiet_start", "quiet_end", "timezone", "confirm"]
PROMPTS = {
    "title": ("Tiket nomi?", "Название заявки?"),
    "vehicle": ("Avtomobil raqamini tanlang:", "Выберите номер автомобиля:"),
    "current_location": ("Hozirgi joyingizni Telegram lokatsiyasi, Google Maps yoki Yandex Maps havolasi bilan yuboring. Shahar nomini yozish ham mumkin.", "Отправьте текущую геопозицию Telegram, ссылку Google Maps или Яндекс Карт. Можно написать город."),
    "origins": ("Qayerlardan yuk olasiz? Telegram lokatsiyasi, Google Maps yoki Yandex Maps havolasini bittadan yuboring, oxirida Tayyor bosing. Yoki shaharlarni yozing: Toshkent, Chirchiq", "Откуда заберёте груз? Отправляйте геопозиции Telegram или ссылки Google Maps / Яндекс Карт по одной, затем нажмите Готово. Или напишите города через запятую."),
    "origin_points": ("Shu yuklash joyining Telegram lokatsiyasi yoki Google Maps / Yandex Maps havolasini yuboring. Faqat shahar bo‘yicha izlash uchun O‘tkazib yuborish bosing.", "Отправьте геопозицию Telegram или ссылку Google Maps / Яндекс Карт для этого места погрузки. Для поиска по городу нажмите Пропустить."),
    "origin_radius": ("Yuklash joylari atrofidagi radius (km)? Faqat shahar mosligi uchun 0.", "Радиус вокруг мест погрузки (км)? 0 — совпадение города."),
    "route_mode": ("Yo‘nalish turini tanlang.", "Выберите тип маршрута."),
    "destinations": ("Boradigan joylarni Telegram lokatsiyasi, Google Maps yoki Yandex Maps havolasi bilan bittadan yuboring, oxirida Tayyor bosing. Yoki shaharlarni vergul bilan yozing. Istalgan yo‘nalish uchun -.", "Отправляйте назначения геопозицией Telegram или ссылкой Google Maps / Яндекс Карт по одному, затем нажмите Готово. Или напишите города через запятую. Любое направление — -."),
    "destination_points": ("Shu manzilning Telegram lokatsiyasi yoki Google Maps / Yandex Maps havolasini yuboring. Faqat shahar bo‘yicha izlash uchun O‘tkazib yuborish bosing.", "Отправьте геопозицию Telegram или ссылку Google Maps / Яндекс Карт для этого назначения. Для поиска по городу нажмите Пропустить."),
    "prices": ("Har manzil uchun eng kam reys/tonna narxi, shaharlar tartibida vergul bilan. Masalan: 3000000, 5000000. Manzil yo‘q bo‘lsa -.", "Минимальные цены по назначениям через запятую в порядке городов. Например: 3000000, 5000000. Если нет — -."),
    "etas": ("Har yo‘nalishda yuklashga yetib borish uchun necha soat kerak? Vergul bilan: 1, 2. Yoki - (0 soat).", "Часы до погрузки по каждому направлению: 1, 2. Или - (0 часов)."),
    "priorities": ("Manzillar ustuvorligi, vergul bilan: 1, 2 (1 — eng afzal). Yoki -.", "Приоритеты через запятую: 1, 2 (1 — предпочтительный). Или -."),
    "radii": ("Manzillar atrofida radius km, vergul bilan: 30, 0. Yoki -.", "Радиусы назначений в км через запятую: 30, 0. Или -."),
    "ready_at": ("Qachondan tayyorsiz? YYYY-MM-DD HH:MM (Toshkent vaqti), yoki hozir uchun -.", "Когда готовы? YYYY-MM-DD HH:MM (Ташкент), или - для текущего времени."),
    "expires_at": ("Necha soat yuk qidirasiz? 1–720.", "Сколько часов искать груз? 1–720."),
    "available_tons": ("Mashinaning bo‘sh sig‘imi, tonna?", "Свободная грузоподъёмность, тонн?"),
    "partial_load": ("Qo‘shimcha yuk olasizmi? ha / yoq. Yo‘l-yo‘lakay yuklar uchun ordered va oraliq shaharlarni tanlang.", "Берёте догруз? да / нет. Для попутных грузов выберите ordered и промежуточные города."),
    "currency": ("Valyuta: UZS / USD", "Валюта: UZS / USD"),
    "price_basis": ("Narx butun reys uchunmi yoki tonnasigami?", "Цена за рейс или за тонну?"),
    "min_price": ("Umumiy eng kam narx? Istalgan yo‘nalishda shu narx ishlaydi.", "Общая минимальная цена? Используется для любого направления."),
    "match_mode": ("Qaysi yuklar haqida xabar berilsin?", "О каких совпадениях уведомлять?"),
    "waypoints": ("Oraliq joylarni ham Telegram lokatsiyasi yoki Google Maps / Yandex Maps havolasi bilan yuboring, oxirida Tayyor bosing. Shaharlarni yozish yoki - bilan o‘tkazish ham mumkin.", "Отправляйте промежуточные точки геопозицией Telegram или ссылками Google Maps / Яндекс Карт, затем Готово. Можно написать города через запятую или - для пропуска."),
    "notes": ("Qo‘shimcha izoh yoki -.", "Примечание или -."),
    "name": ("Mashina nomi? Masalan: Isuzu 01", "Название машины? Например: Isuzu 01"),
    "kind": ("Mashina turini tanlang.", "Выберите тип машины."),
    "capacity_tons": ("Maksimal sig‘im, tonna?", "Максимальная грузоподъёмность, тонн?"),
    "volume_m3": ("Hajmi m³ yoki -.", "Объём м³ или -."),
    "plate": ("Davlat raqami yoki -.", "Госномер или -."),
    "language": ("Til: uz / ru", "Язык: uz / ru"),
    "telegram_enabled": ("Telegram xabarlari: ha / yoq", "Уведомления Telegram: да / нет"),
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
    names = {"title": ("Tiket", "Заявка"), "name": ("Mashina", "Машина"), "capacity_tons": ("Sig‘im (t)", "Грузоподъёмность (т)"), "volume_m3": ("Hajm (m³)", "Объём (м³)"), "plate": ("Davlat raqami", "Госномер"), "available_tons": ("Bo‘sh sig‘im (t)", "Свободная грузоподъёмность (т)"), "min_price": ("Eng kam narx", "Минимальная цена"), "currency": ("Valyuta", "Валюта"), "notes": ("Izoh", "Примечание"), "quiet_start": ("Tinch vaqt boshlanishi", "Начало тихих часов"), "quiet_end": ("Tinch vaqt tugashi", "Конец тихих часов"), "partial_interval_minutes": ("Jamlanma oralig‘i (daqiqa)", "Интервал подборки (минут)"), "timezone": ("Vaqt zonasi", "Часовой пояс"), "language": ("Til", "Язык")}
    for key, titles in names.items():
        if key in data:
            lines.append(f"{titles[int(ru)]}: {data[key] or '—'}")
    for key in ("route_mode", "price_basis", "match_mode", "kind"):
        if key in data:
            lines.append(label(data[key], ru))
    for key, titles in [("origins", ("Yuklash", "Погрузка")), ("waypoints", ("Oraliq", "Через")), ("destinations", ("Manzil", "Назначение"))]:
        for place in data.get(key, []):
            line = f"{titles[int(ru)]}: {place['name']} · {place.get('radius_km', 0)} km"
            if "min_price" in place:
                line += f" · {place['min_price']} {data.get('currency', '')}"
            if key == "destinations":
                line += f" · {place.get('eta_hours', 0)} h · {'Приоритет' if ru else 'Ustuvorlik'} {place.get('priority', 1)}"
            lines.append(line)
            if place.get("lat") is not None:
                lines.append(place.get("source_url") or f"https://www.google.com/maps/search/?api=1&query={place['lat']},{place['lon']}")
    if data.get("vehicle"):
        vehicle = Vehicle.objects.filter(pk=data['vehicle'], owner=account.owner).first()
        lines.append(f"🚛 {vehicle.name if vehicle else '—'}")
    if data.get("current_location"):
        place = data["current_location"]
        lines.append(f"📍 {place.get('name', '')}")
        if place.get("lat") is not None:
            lines.append(place.get("source_url") or f"https://www.google.com/maps/search/?api=1&query={place['lat']},{place['lon']}")
    for key, title in [("ready_at", "🕒"), ("expires_at", "⏰")]:
        if data.get(key):
            lines.append(f"{title} {datetime.fromisoformat(data[key]).astimezone(ZoneInfo('Asia/Tashkent')):%Y-%m-%d %H:%M} (Toshkent)")
    if "partial_load" in data:
        lines.append(("Догруз: " if ru else "Qo‘shimcha yuk: ") + label("ha" if data["partial_load"] else "yoq", ru))
    if "telegram_enabled" in data:
        lines.append("Telegram: " + label("ha" if data["telegram_enabled"] else "yoq", ru))
    return "\n".join(lines)


def steps(state):
    return TICKET_STEPS if state["flow"] == "ticket" else VEHICLE_STEPS if state["flow"] == "vehicle" else PREFERENCE_STEPS


def public_keyboard():
    rows = [[{"text": "🔗 Akkauntni ulash / Подключить аккаунт", "callback_data": "nav:link"}]]
    site = os.getenv("PUBLIC_SITE_URL", "").rstrip("/")
    if site.startswith("https://"):
        rows.append([{"text": "🌐 Sayt / Сайт", "url": f"{site}/driver/tickets"}])
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
    if not state.get("pending_place"):
        choices = {"route_mode": ["alternatives", "ordered", "anywhere"], "kind": ["tent", "van", "refrigerator", "isothermal", "flatbed", "tanker", "dump", "lowbed", "container", "other"], "currency": ["UZS", "USD"], "price_basis": ["trip", "ton"], "match_mode": ["any_two", "route", "full"], "partial_load": ["ha", "yoq"], "telegram_enabled": ["ha", "yoq"], "partial_interval_minutes": ["0", "15", "30", "60"], "language": ["uz", "ru"], "expires_at": ["12", "24", "72", "168"], "origin_radius": ["0", "10", "25", "50", "100"]}
        if key == "vehicle":
            rows += [[button(str(v.pk), f"🚛 {v.name} · {v.capacity_tons} t")] for v in Vehicle.objects.filter(owner=account.owner)]
            rows.append([{"text": "➕ Добавить машину" if ru else "➕ Mashina qo‘shish", "callback_data": "nav:vehicle"}])
        elif key == "confirm":
            rows.append([button("ha", "✅ Сохранить" if ru else "✅ Saqlash")])
        elif key in choices:
            values = choices[key]
            rows += [[button(v) for v in values[i:i+2]] for i in range(0, len(values), 2)]
        if key in ("current_location", "origins", "destinations", "waypoints", "origin_points", "destination_points"):
            rows.append([button("location", "📍 Отправить точку" if ru else "📍 Lokatsiya yuborish"), button("maps", "🗺 Ссылка карты" if ru else "🗺 Xarita havolasi")])
        if key in ("origins", "destinations", "waypoints"):
            rows.append([button("Tayyor", "✅ Готово" if ru else "✅ Tayyor")])
        if key in ("origin_points", "destination_points"):
            rows.append([button("O‘tkazib yuborish", "⏭ Пропустить" if ru else "⏭ O‘tkazib yuborish")])
        elif key in ("current_location", "destinations", "waypoints", "notes", "volume_m3", "plate", "quiet_start", "quiet_end", "prices", "etas", "priorities", "radii"):
            rows.append([button("-", "⏭ Пропустить" if ru else "⏭ O‘tkazib yuborish")])
        elif key == "ready_at":
            rows.append([button("-", "🕒 Сейчас" if ru else "🕒 Hozir")])
        if state.get("instance") and key != "confirm":
            rows.append([button(".", "Оставить значение" if ru else "Avvalgi qiymatni saqlash")])
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
    if state.get("pending_place"):
        return say(account, "Bu joy qaysi shaharda? Shahar nomini yozing — yuklarni shahar bo‘yicha ham topish uchun.", "В каком городе эта точка? Напишите город — он нужен и для поиска грузов по названию.", **kwargs)
    if key in ("origin_points", "destination_points"):
        places = state["data"]["origins" if key == "origin_points" else "destinations"]
        index = next((i for i, place in enumerate(places) if i >= state.get("point_index", 0) and place.get("lat") is None), len(places))
        state["point_index"] = index
        if index >= len(places):
            state.pop("point_index", None)
            state["index"] += 1
            account.save(update_fields=["state"])
            return prompt(account)
        account.save(update_fields=["state"])
        uz = f"📍 {index + 1}/{len(places)}: {places[index]['name']}\n" + uz
        ru = f"📍 {index + 1}/{len(places)}: {places[index]['name']}\n" + ru
    if key in ("origins", "destinations", "waypoints") and state.get("collecting_places") == key:
        names = "\n" + "\n".join(f"✓ {place['name']}" for place in state["data"].get(key, []))
        uz += names
        ru += names
    if key == "vehicle":
        vehicles = list(Vehicle.objects.filter(owner=account.owner))
        if not vehicles:
            return say(account, "Avval Mashina qo‘shish tugmasi orqali avtomobil kiriting.", "Сначала добавьте автомобиль кнопкой Добавить машину.")
        names = "\n" + "\n".join(f"{v.pk}: {v.name} · {v.capacity_tons} t" for v in vehicles)
        uz += names
        ru += names
    if key == "confirm":
        summary = confirmation(account)
        say(account, summary)
    return say(account, uz, ru, **kwargs)


def parse_answer(key, text, message, data, state=None):
    state = state if state is not None else {}
    if key in ("route_mode", "price_basis", "match_mode", "kind", "partial_load", "telegram_enabled"):
        for value, labels in OPTION_LABELS.items():
            if text in labels:
                text = value
                break
    def number(value):
        result = Decimal(value)
        if not result.is_finite() or result < 0:
            raise ValueError()
        return str(result)
    if key in ("origins", "destinations", "waypoints"):
        if text in ("Tayyor", "Готово"):
            if not data.get(key):
                raise LocationError("empty")
            state.pop("collecting_places", None)
            return
        if text == "-":
            if key == "origins":
                raise LocationError("empty")
            data[key] = []
            state.pop("collecting_places", None)
            return
        is_point = bool(message.get("location") or message.get("venue") or "http" in text)
        if is_point or state.get("collecting_places") == key:
            place = parse_location(text, message)
            existing = data.get(key, []) if state.get("collecting_places") == key else []
            if len(existing) >= 10:
                raise LocationError("limit")
            data[key] = existing
            state["collecting_places"] = key
            if place.get("lat") is not None and (place["name"] == "GPS" or message.get("venue")):
                state["pending_place"] = place
            else:
                existing.append(place)
            return False
        places = [{"name": name.strip(), "radius_km": 0} for name in text.split(",") if name.strip()]
        if not places or len(places) > 10 or any(len(p["name"]) > 150 for p in places):
            raise LocationError("name")
        data[key] = places
    elif key in ("origin_points", "destination_points"):
        places = data["origins" if key == "origin_points" else "destinations"]
        index = state.get("point_index", 0)
        if index >= len(places):
            return
        if text == "-":
            state["point_index"] = len(places)
            return False
        if text in ("O‘tkazib yuborish", "Пропустить"):
            places[index].pop("lat", None)
            places[index].pop("lon", None)
            places[index].pop("source_url", None)
        else:
            place = parse_location(text, message)
            if place.get("lat") is None:
                raise LocationError("pin")
            places[index].update({k: v for k, v in place.items() if k in ("lat", "lon", "source_url")})
        state["point_index"] = index + 1
        return False
    elif key == "origin_radius":
        radius = float(number(text))
        if radius > 500:
            raise ValueError()
        for place in data["origins"]:
            place["radius_km"] = radius
    elif key in ("prices", "etas", "priorities", "radii"):
        places = data["destinations"]
        if text == "-":
            return
        values = text.split(",")
        if len(values) != len(places):
            raise ValueError()
        field = {"prices": "min_price", "etas": "eta_hours", "priorities": "priority", "radii": "radius_km"}[key]
        for place, value in zip(places, values):
            place[field] = number(value.strip()) if key == "prices" else float(number(value.strip()))
    elif key == "current_location":
        data[key] = {} if text == "-" else parse_location(text, message)
    elif key == "ready_at":
        data[key] = (timezone.now() if text == "-" else datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Tashkent"))).isoformat()
    elif key == "expires_at":
        hours = int(text)
        if not 1 <= hours <= 720:
            raise ValueError()
        data[key] = (timezone.now() + timedelta(hours=hours)).isoformat()
    elif key in ("partial_load", "telegram_enabled"):
        if text.casefold() not in ("ha", "yoq", "да", "нет"):
            raise ValueError()
        data[key] = text.casefold() in ("ha", "да")
    elif key in ("vehicle", "partial_interval_minutes"):
        data[key] = int(text)
    elif key in ("capacity_tons", "available_tons", "min_price", "volume_m3"):
        data[key] = None if key == "volume_m3" and text == "-" else number(text)
    elif key in ("quiet_start", "quiet_end"):
        data[key] = None if text == "-" else datetime.strptime(text, "%H:%M").time().isoformat()
    else:
        choices = {"kind": ['tent', 'van', 'refrigerator', 'isothermal', 'flatbed', 'tanker', 'dump', 'lowbed', 'container', 'other'], "currency": ["UZS", "USD"], "price_basis": ["trip", "ton"], "match_mode": ["any_two", "route", "full"], "route_mode": ["alternatives", "ordered", "anywhere"], "language": ["uz", "ru"]}
        if key in choices and text not in choices[key]:
            raise ValueError()
        data[key] = "" if text == "-" else text


def callback(account, query):
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
    text = message.get("text", "").strip()[:4000]
    if not query and text.startswith("/start "):
        account = bind_account(text.split(maxsplit=1)[1], chat_id)
        if account:
            say(account, "Akkaunt ulandi. Kerakli bo‘limni tugmalardan tanlang.", "Аккаунт подключён. Выберите раздел кнопками.")
        else:
            call("sendMessage", chat_id=chat_id, text="Havola yaroqsiz yoki muddati tugagan. Saytdan yangi ulash havolasini oling. / Ссылка недействительна. Получите новую на сайте.", reply_markup=public_keyboard())
        return
    account = TelegramAccount.objects.select_related("owner").filter(chat_id=chat_id, owner__role="driver", owner__is_active=True).first()
    if not account:
        if query:
            call("answerCallbackQuery", callback_query_id=query["id"])
        call("sendMessage", chat_id=chat_id, text="Saytda driver bo‘lib kiring → Tiketlarim → Xabar sozlamalari → Telegramni ulash. / Войдите на сайт как водитель → Мои заявки → Настройки уведомлений → Подключить Telegram.", reply_markup=public_keyboard())
        return
    if query:
        payload = query.get("data", "")
        if not payload.startswith(("nav:", "u:")):
            return callback(account, query)
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
        return handle_update({"message": {"chat": message["chat"], "from": {"id": sender}, "text": text}})
    if text in ("/cancel", "/start", "/help"):
        account.state = {}
        account.save(update_fields=["state"])
        if text == "/start":
            removed = call("sendMessage", chat_id=account.chat_id, text="🏠 Menyu / Меню", reply_markup={"remove_keyboard": True})
            return call("editMessageReplyMarkup", chat_id=account.chat_id, message_id=removed["message_id"], reply_markup=inline_keyboard(account, Preference.objects.get_or_create(owner=account.owner)[0].language == "ru"))
        return say(account, "Kerakli bo‘limni tanlang.", "Выберите раздел.")
    if text == "/vehicles":
        vehicles = list(Vehicle.objects.filter(owner=account.owner))
        pref, _ = Preference.objects.get_or_create(owner=account.owner)
        ru = pref.language == "ru"
        lines = [f"🚛 {v.name} · {label(v.kind, ru)} · {v.capacity_tons} t" for v in vehicles]
        rows = [[{"text": "➕ Добавить машину" if ru else "➕ Mashina qo‘shish", "callback_data": "nav:vehicle"}]] + menu_rows(ru)
        return say(account, "\n".join(lines) or "Hali mashina qo‘shilmagan.", "\n".join(lines) or "Машины пока не добавлены.", reply_markup={"inline_keyboard": rows})
    if text == "/tickets":
        for ticket in Ticket.objects.filter(owner=account.owner)[:20]:
            say(account, f"#{ticket.pk} {ticket.title}\n{ticket.status}\n{ticket.expires_at:%Y-%m-%d %H:%M} UTC", reply_markup={"inline_keyboard": [[{"text": "Pauza / Пауза", "callback_data": f"pause:{ticket.pk}"}, {"text": "Davom / Продолжить", "callback_data": f"resume:{ticket.pk}"}], [{"text": "+7 kun / дней", "callback_data": f"extend:{ticket.pk}"}, {"text": "Yopish / Закрыть", "callback_data": f"close:{ticket.pk}"}], [{"text": "Tahrirlash / Изменить", "callback_data": f"nav:edit:{ticket.pk}"}, {"text": "Qaytish / Обратно", "callback_data": f"nav:return:{ticket.pk}"}], [{"text": "🏠 Menyu / Меню", "callback_data": "nav:menu"}]]})
        return say(account, "Tiketni yuqoridagi tugmalar orqali boshqaring yoki yangi tiket oching.", "Управляйте заявками кнопками выше или создайте новую.")
    if text in ("/ticket", "/vehicle", "/settings") or text.startswith("/edit "):
        flow = "vehicle" if text == "/vehicle" else "preferences" if text == "/settings" else "ticket"
        state = {"flow": flow, "index": 0, "data": {"match_mode": "any_two"} if flow == "ticket" else {}}
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
        state.pop("pending_place", None)
        state.pop("collecting_places", None)
        state.pop("point_index", None)
        state["index"] = max(0, state["index"] - 1)
        account.save(update_fields=["state"])
        return prompt(account)
    key = steps(state)[state["index"]]
    try:
        if key == "confirm":
            if text.casefold() not in ("ha", "да"):
                return prompt(account)
            ctx = {"request": SimpleNamespace(user=account.owner)}
            if state["flow"] == "ticket":
                instance = Ticket.objects.filter(pk=state.get("instance"), owner=account.owner).first()
                if instance is None and Ticket.objects.filter(owner=account.owner, status__in=["active", "paused"]).count() >= 20:
                    raise ValidationError("At most 20 active or paused tickets.")
                serializer = TicketSerializer(instance, data=state["data"], context=ctx)
            elif state["flow"] == "vehicle":
                serializer = VehicleSerializer(data=state["data"])
            else:
                pref, _ = Preference.objects.get_or_create(owner=account.owner)
                serializer = PreferenceSerializer(pref, data=state["data"], partial=True)
            serializer.is_valid(raise_exception=True)
            obj = serializer.save(owner=account.owner)
            if isinstance(obj, Ticket):
                if not state.get("instance"):
                    notify(obj, "ticket_created", f"ticket:{obj.pk}")
                scan_ticket(obj.pk)
            account.state = {}
            account.save(update_fields=["state"])
            return say(account, "✅ Saqlandi. Kerakli bo‘limni tanlang.", "✅ Сохранено. Выберите раздел.")
        if state.get("pending_place"):
            place = parse_location(text)
            if "lat" in place or text in ("-", "Tayyor", "Готово"):
                raise LocationError("name")
            state["pending_place"]["name"] = place["name"]
            state["data"][key].append(state.pop("pending_place"))
            account.save(update_fields=["state"])
            return prompt(account)
        if text != "." or not state.get("instance"):
            if parse_answer(key, text, message, state["data"], state) is False:
                account.save(update_fields=["state"])
                return prompt(account)
        state.pop("collecting_places", None)
        state.pop("point_index", None)
        state["index"] += 1
        account.save(update_fields=["state"])
        prompt(account)
    except LocationError as exc:
        errors = {
            "network": ("Xarita havolasini ochib bo‘lmadi. Qayta yuboring yoki Telegram lokatsiyasini yuboring.", "Не удалось открыть ссылку. Повторите или отправьте геопозицию Telegram."),
            "name": ("Shahar nomini yozing.", "Напишите название города."),
            "empty": ("Avval kamida bitta joy yuboring.", "Сначала отправьте хотя бы одну точку."),
            "limit": ("Ko‘pi bilan 10 ta joy qo‘shish mumkin. Tayyor bosing.", "Можно добавить до 10 точек. Нажмите Готово."),
        }
        uz, ru = errors.get(str(exc), ("Google Maps yoki Yandex Maps’da aniq nuqtani tanlab Ulashish havolasini yuboring. Yoki Telegram lokatsiyasini yuboring.", "Выберите точку в Google Maps или Яндекс Картах и отправьте ссылку Поделиться. Или отправьте геопозицию Telegram."))
        say(account, uz, ru)
    except (ValueError, TypeError, InvalidOperation, ValidationError) as exc:
        detail = str(exc.detail)[:600] if isinstance(exc, ValidationError) else ""
        say(account, f"Qiymatni tekshiring. /back bilan qaytishingiz mumkin. {detail}", f"Проверьте значение. Можно вернуться: /back. {detail}")
