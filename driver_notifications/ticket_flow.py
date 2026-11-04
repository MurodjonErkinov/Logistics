"""Defaults shared by the four-step website and Telegram ticket flows."""

from datetime import timedelta

from django.utils import timezone


def simple_ticket_payload(title, vehicle, origins, destinations, anywhere=False):
    now = timezone.now()
    fields = ("name", "lat", "lon", "source_url", "address", "geocoded")
    clean = lambda places: [{key: value for key, value in place.items() if key in fields} for place in places]
    origins = clean(origins)
    destinations = [] if anywhere else clean(destinations)
    return {
        "title": title, "vehicle": vehicle.pk, "origins": origins, "destinations": destinations,
        "route_mode": "anywhere" if anywhere else "alternatives",
        "current_location": origins[0] if origins else {},
        "ready_at": now.isoformat(), "expires_at": (now + timedelta(days=7)).isoformat(),
        "available_tons": str(vehicle.capacity_tons), "status": "active", "waypoints": [],
        "partial_load": False, "min_price": "0", "currency": "UZS", "price_basis": "trip",
        "match_mode": "route", "notes": "",
    }
