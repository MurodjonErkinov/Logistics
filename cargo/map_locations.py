"""Resolve listing names for an approximate map, independently of matching."""

import hashlib
import json
import math
import os
import threading
import time
import urllib.parse
import urllib.request

from django.core.cache import cache

_lock = threading.Lock()
_last_request = 0.0


def city_point(name):
    endpoint = os.getenv("GEOCODER_SEARCH_URL", "https://photon.komoot.io/api/").strip()
    if not endpoint:
        return None
    key = "load-map:" + hashlib.sha256(f"{endpoint}:{name.casefold().strip()}".encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached or None
    global _last_request
    result = None
    try:
        with _lock:
            cached = cache.get(key)
            if cached is not None:
                return cached or None
            time.sleep(max(0, 1.1 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
            query = urllib.parse.urlencode({"q": name, "limit": 1, "lang": "en", "osm_tag": "place"})
            request = urllib.request.Request(endpoint + ("&" if "?" in endpoint else "?") + query, headers={"User-Agent": "YukFlow/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                raw = response.read(128001)
            if len(raw) > 128000:
                raise ValueError("Geocoder response too large")
            feature = json.loads(raw)["features"][0]
            lon, lat = map(float, feature["geometry"]["coordinates"][:2])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Invalid map coordinates")
            properties = feature.get("properties", {})
            label = ", ".join(str(properties[k]) for k in ("name", "state", "country") if properties.get(k))
            result = {"lat": lat, "lon": lon, "approximate": True, "label": label[:300] or name}
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        pass
    cache.set(key, result or {}, 30 * 86400 if result else 300)
    return result


def load_map_points(load):
    points = {}
    for key in ("origin", "destination"):
        lat, lon = getattr(load, f"{key}_lat"), getattr(load, f"{key}_lon")
        points[key] = {"lat": float(lat), "lon": float(lon), "approximate": False, "label": getattr(load, key)} if lat is not None and lon is not None else city_point(getattr(load, key))
    return points
