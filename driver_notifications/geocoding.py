"""Resolve user-selected coordinates to a city without another bot question."""

import hashlib
import json
import os
import threading
import time
import urllib.parse
import urllib.request

from django.core.cache import cache

from .locations import LocationError


_request_lock = threading.Lock()
_last_request = 0.0


def reverse_place(lat, lon):
    endpoint = os.getenv("GEOCODER_REVERSE_URL", "https://photon.komoot.io/reverse").strip()
    if not endpoint:
        raise LocationError("geocoding")
    key = "driver-place:" + hashlib.sha256(f"{endpoint}:{lat:.5f}:{lon:.5f}".encode()).hexdigest()
    cached = cache.get(key)
    if cached:
        return cached
    query = urllib.parse.urlencode({"lat": lat, "lon": lon, "lang": "en", "limit": 1, "radius": 2})
    request = urllib.request.Request(
        endpoint + ("&" if "?" in endpoint else "?") + query,
        headers={"User-Agent": "YukFlow/1.0 (+https://t.me/murodjonerkinov)", "Accept": "application/json"},
    )
    global _last_request
    try:
        with _request_lock:
            cached = cache.get(key)
            if cached:
                return cached
            time.sleep(max(0, 1.1 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
            with urllib.request.urlopen(request, timeout=6) as response:
                raw = response.read(128_001)
            if len(raw) > 128_000:
                raise LocationError("geocoding")
            payload = json.loads(raw)
        properties = payload["features"][0]["properties"]
        city = properties.get("city") or properties.get("town") or properties.get("village")
        if not city and properties.get("osm_value") in ("city", "town", "village", "hamlet"):
            city = properties.get("name")
        if not isinstance(city, str) or not city.strip():
            raise LocationError("geocoding")
        parts = []
        for field in ("name", "street", "housenumber", "city", "district", "state", "country"):
            value = properties.get(field)
            if isinstance(value, str) and value.strip() and value not in parts:
                parts.append(value)
        result = {"name": city.strip()[:150], "address": ", ".join(parts)[:300], "geocoded": True}
        cache.set(key, result, 30 * 24 * 60 * 60)
        return result
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        raise LocationError("geocoding") from None
