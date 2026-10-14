import os
from urllib.parse import quote, urlsplit

from django.core.exceptions import ImproperlyConfigured

from .settings import *

DEBUG = False
site = urlsplit(os.environ.get("PUBLIC_SITE_URL", ""))
if site.scheme != "https" or not site.hostname or site.hostname in ("localhost", "127.0.0.1"):
    raise ImproperlyConfigured("Set PUBLIC_SITE_URL to your public HTTPS domain.")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("replace-"):
    raise ImproperlyConfigured("Set a random DJANGO_SECRET_KEY of at least 50 characters.")
for key in ("POSTGRES_PASSWORD", "REDIS_PASSWORD"):
    value = os.environ.get(key, "")
    if len(value) < 16 or value.startswith("replace-"):
        raise ImproperlyConfigured(f"Set a random {key} of at least 16 characters.")
ALLOWED_HOSTS = [site.hostname, "web", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = [f"https://{site.netloc}"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_PATH = site.path.rstrip("/") or "/"
CSRF_COOKIE_PATH = SESSION_COOKIE_PATH
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
TRUST_PROXY_ADDRESS = True
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": f"redis://:{quote(os.environ['REDIS_PASSWORD'], safe='')}@cache:6379/1", "KEY_PREFIX": "logistics"}}
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
