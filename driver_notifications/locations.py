import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request


class LocationError(ValueError):
    pass


GOOGLE_HOSTS = {"google.com", "www.google.com", "maps.google.com", "maps.google.ru", "www.google.ru", "www.google.co.uz", "google.co.uz", "maps.app.goo.gl", "goo.gl"}
YANDEX_HOSTS = {"yandex.ru", "www.yandex.ru", "yandex.com", "www.yandex.com", "yandex.uz", "www.yandex.uz", "maps.yandex.ru", "maps.yandex.com", "yandex.kz", "www.yandex.kz", "yandex.by", "www.yandex.by", "yandex.eu", "www.yandex.eu", "yandex.com.tr", "www.yandex.com.tr"}
SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl", "clck.ru"}
NUMBER = r"[-+]?\d+(?:\.\d+)?"
PAIR = re.compile(rf"^\s*({NUMBER})\s*[, ]\s*({NUMBER})\s*$")


def checked_url(url):
    if len(url) > 2048:
        raise LocationError("link")
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise LocationError("link")
    if host not in GOOGLE_HOSTS | YANDEX_HOSTS | {"clck.ru"}:
        raise LocationError("link")
    if host in GOOGLE_HOSTS - SHORT_HOSTS and not (parsed.path.startswith("/maps") or host.startswith("maps.google.") and parsed.path in ("", "/")):
        raise LocationError("link")
    if host == "goo.gl" and not parsed.path.startswith("/maps/"):
        raise LocationError("link")
    if host in YANDEX_HOSTS and not parsed.path.startswith("/maps"):
        raise LocationError("link")
    return parsed


def point(lat, lon, name="GPS", source_url=None):
    lat, lon = float(lat), float(lon)
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise LocationError("coordinates")
    result = {"name": name[:150], "lat": lat, "lon": lon, "radius_km": 0}
    if source_url:
        result["source_url"] = source_url
    return result


def pair(value, reverse=False):
    match = PAIR.fullmatch(value)
    if not match:
        return None
    first, second = match.groups()
    return point(second, first) if reverse else point(first, second)


def coordinates_from_url(url):
    parsed = checked_url(url)
    query = urllib.parse.parse_qs(parsed.query)
    decoded = urllib.parse.unquote(url)
    if parsed.hostname in YANDEX_HOSTS:
        for key in ("whatshere[point]", "pt"):
            if key in query:
                value = pair(",".join(query[key][0].split(",")[:2]), reverse=True)
                if value:
                    return value
        if "/org/" not in parsed.path and "ll" in query:
            return pair(query["ll"][0], reverse=True)
        if "text" in query:
            return pair(query["text"][0])
    else:
        match = re.search(rf"!3d({NUMBER})!4d({NUMBER})", decoded)
        if match:
            return point(*match.groups())
        for key in ("query", "q", "destination", "daddr"):
            if key in query:
                value = pair(query[key][0].removeprefix("loc:"))
                if value:
                    return value
        if "/place/" not in parsed.path and "/dir/" not in parsed.path:
            match = re.search(rf"@({NUMBER}),({NUMBER})(?:,|$)", decoded)
            if match:
                return point(*match.groups())
    return None


class SafeRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def resolve_link(url):
    checked_url(url)
    found = coordinates_from_url(url)
    if found:
        return found
    opener = urllib.request.build_opener(SafeRedirects(), urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
    try:
        with opener.open(request, timeout=8) as response:
            final = response.geturl()
            checked_url(final)
            found = coordinates_from_url(final)
            if found:
                return found
            if urllib.parse.urlsplit(final).hostname not in (GOOGLE_HOSTS | YANDEX_HOSTS) - SHORT_HOSTS:
                raise LocationError("link")
            html = response.read(512_001)
            if len(html) > 512_000:
                raise LocationError("pin")
            html = html.decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError):
        raise LocationError("network") from None
    for block in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, flags=re.S | re.I):
        try:
            payload = json.loads(block)
        except ValueError:
            continue
        objects = payload if isinstance(payload, list) else [payload]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            geo = obj if obj.get("@type") == "GeoCoordinates" else obj.get("geo", {})
            if isinstance(geo, dict) and "latitude" in geo and "longitude" in geo:
                return point(geo["latitude"], geo["longitude"])
    raise LocationError("pin")


def parse_location(text, message=None):
    message = message or {}
    venue = message.get("venue", {})
    location = message.get("location") or venue.get("location")
    if location:
        return point(location["latitude"], location["longitude"], venue.get("title") or "GPS")
    urls = re.findall(r"https?://[^\s<>]+", text)
    if urls:
        if len(urls) != 1:
            raise LocationError("one_at_a_time")
        url = urls[0]
        result = resolve_link(url)
        name = text.replace(url, "").strip(" \n—-:")
        if name:
            result["name"] = name[:150]
        result["source_url"] = url
        return result
    if text.startswith(("www.", "maps.", "geo:", "http")):
        raise LocationError("link")
    if PAIR.fullmatch(text):
        return pair(text)
    if not text or len(text) > 150:
        raise LocationError("name")
    return {"name": text, "radius_km": 0}
