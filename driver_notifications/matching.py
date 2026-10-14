import math
import re
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone


def normalize(text):
    text = re.sub(r"[^\w]+", " ", text.casefold()).strip()
    aliases = {"ташкент": "toshkent", "tashkent": "toshkent", "самарканд": "samarqand", "samarkand": "samarqand", "бухара": "buxoro", "bukhara": "buxoro", "наманган": "namangan", "андижан": "andijon", "andijan": "andijon", "навои": "navoiy", "navoi": "navoiy", "фергана": "fargona", "farg ona": "fargona", "нукус": "nukus", "карши": "qarshi", "термез": "termiz", "ургенч": "urganch"}
    return aliases.get(text, text)


def vehicle_kind(text):
    text = text.casefold()
    for kind, pattern in [("isothermal", r"izoterm|isotherm|изотерм"), ("dump", r"samosval|самосвал"), ("lowbed", r"tral|трал|lowbed"), ("container", r"konteyner|container|контейнер"), ("refrigerator", r"ref|реф|холод"), ("tent", r"tent|тент|тэнт"), ("flatbed", r"bort|борт|platform|платформ"), ("tanker", r"cistern|цистер|tanker"), ("van", r"furgon|фургон")]:
        if re.search(pattern, text):
            return kind
    return "unknown"


def distance(a, b):
    if any(p.get(k) is None for p in (a, b) for k in ("lat", "lon")):
        return None
    lat1, lat2 = math.radians(float(a["lat"])), math.radians(float(b["lat"]))
    dlat, dlon = lat2 - lat1, math.radians(float(b["lon"]) - float(a["lon"]))
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def place_matches(wanted, actual):
    radius = wanted.get("radius_km", 0)
    km = distance(wanted, actual)
    if radius:
        return None if km is None else km <= radius
    return normalize(wanted["name"]) == normalize(actual["name"])


def both(a, b):
    return False if a is False or b is False else None if a is None or b is None else True


def either(values):
    return True if True in values else None if None in values else False


def evaluate(ticket, load):
    now = timezone.now()
    if load.status != "open" or ticket.status != "active" or ticket.expires_at <= now:
        return None
    if load.posted_by_id == ticket.owner_id:
        return None
    capacity = load.weight_tons <= min(ticket.available_tons, ticket.vehicle.capacity_tons)
    if not capacity and ticket.match_mode != "any_two":
        return None
    origin = {"name": load.origin, "lat": load.origin_lat, "lon": load.origin_lon}
    destination = {"name": load.destination, "lat": load.destination_lat, "lon": load.destination_lon}
    vehicle = load.vehicle_kind or vehicle_kind(load.vehicle_type)
    checks = {"capacity": capacity, "vehicle": None if vehicle == "unknown" else ticket.vehicle.kind == vehicle}
    choices = sorted(ticket.destinations, key=lambda p: p.get("priority", 1))
    target = next((p for p in choices if place_matches(p, destination) is True), {})
    if ticket.route_mode == "ordered":
        stops = ticket.origins + ticket.waypoints + ticket.destinations
        pairs = [both(place_matches(a, origin), place_matches(b, destination)) for i, a in enumerate(stops) for j, b in enumerate(stops) if i < j]
        checks["route"] = either(pairs) if ticket.partial_load else both(place_matches(stops[0], origin), place_matches(stops[-1], destination))
    else:
        start = either([place_matches(p, origin) for p in ticket.origins])
        finish = True if ticket.route_mode == "anywhere" else either([place_matches(p, destination) for p in choices])
        checks["route"] = False if False in (start, finish) else None if None in (start, finish) else True
    arrival = ticket.ready_at + timedelta(hours=float(target.get("eta_hours", 0)))
    if load.pickup_date:
        local_day = arrival.astimezone(ZoneInfo("Asia/Tashkent")).date()
        checks["time"] = local_day <= load.pickup_date and now.astimezone(ZoneInfo("Asia/Tashkent")).date() <= load.pickup_date <= ticket.expires_at.astimezone(ZoneInfo("Asia/Tashkent")).date()
    else:
        checks["time"] = None
    threshold = Decimal(str(target.get("min_price", ticket.min_price)))
    amount = load.price_amount
    if amount is not None:
        if ticket.price_basis == "ton" and load.price_basis == "trip":
            amount = amount / load.weight_tons
        elif ticket.price_basis == "trip" and load.price_basis == "ton":
            amount = amount * load.weight_tons
    checks["price"] = None if amount is None else load.currency == ticket.currency and amount >= threshold
    if ticket.match_mode != "any_two" and checks["route"] is not True:
        return None
    full = all(v is True for v in checks.values())
    score = sum(checks[k] is True for k in ("route", "vehicle", "time", "price", "capacity"))
    if ticket.match_mode == "full" and not full or score < 2:
        return None
    km = distance(ticket.current_location, origin)
    return {"level": "full" if full else "partial", "checks": checks, "distance_km": round(km, 1) if km is not None else None, "priority": target.get("priority"), "distance_type": "straight_line"}
