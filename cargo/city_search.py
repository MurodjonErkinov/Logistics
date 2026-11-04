"""Small cached searches against a configurable global geocoder."""

import hashlib
import json
import math
import os
import threading
import urllib.parse
import urllib.request

from django.core.cache import cache

_requests = threading.BoundedSemaphore(3)


class CitySearchUnavailable(Exception):
    pass


def search_cities(query, language="en"):
    endpoint = os.getenv("GEOCODER_SEARCH_URL", "https://photon.komoot.io/api/").strip()
    if not endpoint:
        raise CitySearchUnavailable()
    key = "city-search:v1:" + hashlib.sha256(f"{endpoint}:{language}:{query.casefold()}".encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    if not _requests.acquire(blocking=False):
        raise CitySearchUnavailable()
    try:
        # Another caller may already have filled the cache while we were waiting.
        cached = cache.get(key)
        if cached is not None:
            return cached
        params = [("q", query), ("limit", "8"), ("lang", language), ("layer", "city"), ("layer", "locality"), ("layer", "state")]
        request = urllib.request.Request(endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode(params), headers={"User-Agent": "YukFlow/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read(128001)
        if len(raw) > 128000:
            raise ValueError("Geocoder response too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise ValueError("Invalid geocoder response")
        results, seen = [], set()
        for feature in payload["features"][:8]:
            try:
                props = feature["properties"]
                if not isinstance(props, dict):
                    continue
                name = props.get("name") or props.get("city")
                if not isinstance(name, str) or not name.strip():
                    continue
                lon, lat = map(float, feature["geometry"]["coordinates"][:2])
                if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                    continue
                identity = (str(props.get("osm_type", "")), str(props.get("osm_id", "")))
                uid = ":".join(identity) if all(identity) else f"{lat:.6f}:{lon:.6f}"
                if uid in seen:
                    continue
                seen.add(uid)
                context = list(dict.fromkeys(str(props[k]) for k in ("state", "country") if props.get(k) and props[k] != name))
                results.append({"id": uid, "name": name.strip()[:150], "description": ", ".join(context)[:300], "country_code": str(props.get("countrycode") or "")[:2], "lat": lat, "lon": lon})
            except (ValueError, KeyError, IndexError, TypeError):
                continue
        cache.set(key, results, 86400 if results else 300)
        return results
    except (OSError, ValueError, KeyError, TypeError):
        raise CitySearchUnavailable() from None
    finally:
        _requests.release()
